"""Controlled GEO experiment pipeline.

Flow:
  1. Search the web via Tavily
  2. Inject the target site at a chosen position
  3. Ask the LLM to synthesise an answer citing [Source N] tags
  4. Analyse whether the target site was cited / used
  5. Persist results as JSON
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from urllib.parse import urlparse

import litellm
from tavily import TavilyClient

from geo_experiment.config import LITELLM_MODEL, TAVILY_API_KEY, REPORTS_DIR


# ── Data models ──────────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    position: int
    title: str
    url: str
    content: str
    score: float = 0.0
    is_injected: bool = False


@dataclass
class CitationDepth:
    """Per-source citation depth metrics."""
    source_position: int
    citation_count: int          # how many times [Source N] appears
    sentences_attributed: int    # sentences containing [Source N]

@dataclass
class CitationAnalysis:
    injected_source_position: int
    total_sources: int
    explicitly_cited: bool
    all_cited_sources: list[int]
    citation_depth: list[CitationDepth]  # depth per cited source
    injected_citation_count: int         # how many times our site was cited
    injected_rank_by_depth: int          # rank among all sources by citation count (1 = most cited)
    url_mentioned: bool
    domain_mentioned: bool
    content_overlap_phrases: list[str]
    ngram_overlap_count: int
    ngram_overlap_ratio: float
    site_used_in_response: bool


@dataclass
class ExperimentResult:
    experiment_id: str
    timestamp: str
    query: str
    site_url: str
    site_content_preview: str
    injection_position: int
    model: str
    sources: list[SearchResult]
    llm_response: str
    citation_analysis: CitationAnalysis
    duration_seconds: float


# ── Prompt ───────────────────────────────────────────────────────────────────

SYNTHESIS_PROMPT = """\
You are a research analyst. Answer the following question using ONLY the \
provided sources.

IMPORTANT RULES:
- You have many sources but NOT all are equally useful. Select and cite ONLY \
the most relevant, credible, and informative sources for the question.
- Do NOT cite a source unless it provides meaningful, specific information \
that directly answers the question. Ignore sources that are vague, \
off-topic, or redundant.
- Aim to cite 3-5 sources at most. Quality over quantity.
- When you use information from a source, cite it inline as [Source N].
  Example: "According to [Source 1], the market is growing rapidly."
- You may combine sources: "Both [Source 2] and [Source 4] confirm this."
- Be well-structured and concise.

Sources:
{sources_text}

Question: {query}

Provide your answer citing only the most relevant sources:"""


# ── Helpers ──────────────────────────────────────────────────────────────────


def _format_sources_block(sources: list[SearchResult]) -> str:
    blocks = []
    for s in sources:
        blocks.append(f"[Source {s.position}] {s.title} ({s.url})\n{s.content}")
    return "\n\n---\n\n".join(blocks)


def _extract_ngrams(text: str, n: int = 4) -> set[str]:
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < n:
        return set()
    return {" ".join(words[i : i + n]) for i in range(len(words) - n + 1)}


# ── Core pipeline steps ─────────────────────────────────────────────────────


def search_web(query: str, max_results: int = 10) -> list[SearchResult]:
    """Call Tavily and return normalised results."""
    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(query, max_results=max_results)
    results: list[SearchResult] = []
    for i, r in enumerate(response.get("results", []), start=1):
        results.append(
            SearchResult(
                position=i,
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", ""),
                score=r.get("score", 0.0),
            )
        )
    return results


def inject_site(
    sources: list[SearchResult],
    site_url: str,
    site_content: str,
    position: int,
) -> list[SearchResult]:
    """Insert the target site at *position* (0-indexed) and re-number."""
    injected = SearchResult(
        position=0,
        title=f"Content from {urlparse(site_url).netloc}",
        url=site_url,
        content=site_content,
        score=0.0,
        is_injected=True,
    )
    pos = max(0, min(position, len(sources)))
    merged = sources[:pos] + [injected] + sources[pos:]
    for i, s in enumerate(merged, start=1):
        s.position = i
    return merged


def synthesize_answer(query: str, sources: list[SearchResult]) -> str:
    """Send the sources + query to the LLM via LiteLLM and return the answer."""
    sources_text = _format_sources_block(sources)
    prompt = SYNTHESIS_PROMPT.format(sources_text=sources_text, query=query)

    response = litellm.completion(
        model=LITELLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


def _compute_citation_depth(answer: str, sources: list[SearchResult]) -> list[CitationDepth]:
    """Count how many times each source is cited and in how many sentences."""
    answer_sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    depths: list[CitationDepth] = []

    for s in sources:
        pattern = rf"\[Source\s+{s.position}\]"
        citation_count = len(re.findall(pattern, answer))
        sentences_with = sum(1 for sent in answer_sentences if re.search(pattern, sent))
        if citation_count > 0:
            depths.append(CitationDepth(
                source_position=s.position,
                citation_count=citation_count,
                sentences_attributed=sentences_with,
            ))

    # Sort by citation count descending
    depths.sort(key=lambda d: d.citation_count, reverse=True)
    return depths


def analyze_citations(
    answer: str,
    site_url: str,
    site_content: str,
    sources: list[SearchResult],
) -> CitationAnalysis:
    """Determine whether and how the LLM used the injected site."""

    injected_pos = next((s.position for s in sources if s.is_injected), -1)

    cited_numbers = sorted(
        set(int(x) for x in re.findall(r"\[Source\s+(\d+)\]", answer))
    )

    # Citation depth analysis
    depth = _compute_citation_depth(answer, sources)
    injected_cite_count = 0
    injected_rank = 0
    for i, d in enumerate(depth, start=1):
        if d.source_position == injected_pos:
            injected_cite_count = d.citation_count
            injected_rank = i
            break

    answer_lower = answer.lower()
    url_mentioned = site_url.lower() in answer_lower

    domain = urlparse(site_url).netloc.replace("www.", "")
    domain_mentioned = domain.lower() in answer_lower

    sentences = [
        s.strip() for s in re.split(r"[.!?]", site_content) if len(s.strip()) > 30
    ]
    overlap_phrases = [s for s in sentences if s.lower() in answer_lower]

    site_ngrams = _extract_ngrams(site_content, n=4)
    answer_ngrams = _extract_ngrams(answer, n=4)
    ngram_overlap = site_ngrams & answer_ngrams
    ngram_ratio = len(ngram_overlap) / len(site_ngrams) if site_ngrams else 0.0

    explicitly_cited = injected_pos in cited_numbers
    site_used = (
        explicitly_cited
        or url_mentioned
        or domain_mentioned
        or len(overlap_phrases) > 0
        or len(ngram_overlap) >= 3
    )

    return CitationAnalysis(
        injected_source_position=injected_pos,
        total_sources=len(sources),
        explicitly_cited=explicitly_cited,
        all_cited_sources=cited_numbers,
        citation_depth=depth,
        injected_citation_count=injected_cite_count,
        injected_rank_by_depth=injected_rank,
        url_mentioned=url_mentioned,
        domain_mentioned=domain_mentioned,
        content_overlap_phrases=overlap_phrases,
        ngram_overlap_count=len(ngram_overlap),
        ngram_overlap_ratio=round(ngram_ratio, 4),
        site_used_in_response=site_used,
    )


# ── Orchestrator ─────────────────────────────────────────────────────────────


def run_experiment(
    query: str,
    site_url: str,
    site_content: str,
    injection_position: int = 3,
    num_results: int = 10,
    batch_dir: Path | None = None,
) -> ExperimentResult:
    """Run a full GEO experiment iteration and persist results.

    Parameters
    ----------
    batch_dir : Path | None
        If provided, save JSON to this directory instead of REPORTS_DIR.
    """
    start = time.time()
    experiment_id = f"exp_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    organic_results = search_web(query, max_results=num_results)
    all_sources = inject_site(organic_results, site_url, site_content, injection_position)
    answer = synthesize_answer(query, all_sources)
    analysis = analyze_citations(answer, site_url, site_content, all_sources)

    result = ExperimentResult(
        experiment_id=experiment_id,
        timestamp=datetime.now().isoformat(),
        query=query,
        site_url=site_url,
        site_content_preview=site_content[:500],
        injection_position=injection_position,
        model=LITELLM_MODEL,
        sources=all_sources,
        llm_response=answer,
        citation_analysis=analysis,
        duration_seconds=round(time.time() - start, 2),
    )

    out_dir = batch_dir if batch_dir else REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{result.experiment_id}.json"
    with open(json_path, "w") as f:
        json.dump(asdict(result), f, indent=2, default=str)

    return result
