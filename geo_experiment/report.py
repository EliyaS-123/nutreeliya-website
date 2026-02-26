"""Report generation — Rich console output + Markdown file."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from geo_experiment.experiment import ExperimentResult
from geo_experiment.config import REPORTS_DIR

console = Console()


def print_report(result: ExperimentResult) -> None:
    """Pretty-print experiment results to the terminal."""
    analysis = result.citation_analysis

    # ── Header ───────────────────────────────────────────────────────────
    console.print()
    console.print(
        Panel(
            f"[bold]GEO Experiment Report[/bold]\n"
            f"ID: {result.experiment_id}\n"
            f"Time: {result.timestamp}\n"
            f"Model: {result.model}\n"
            f"Duration: {result.duration_seconds}s",
            title="Experiment",
            border_style="blue",
        )
    )

    console.print(f"\n[bold cyan]Query:[/bold cyan] {result.query}")
    console.print(f"[bold cyan]Target Site:[/bold cyan] {result.site_url}")

    # ── Sources table ────────────────────────────────────────────────────
    console.print("\n[bold]Search Results & Sources:[/bold]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", width=40)
    table.add_column("URL", width=50)
    table.add_column("Type", width=10)
    table.add_column("Cited?", width=8)

    for s in result.sources:
        source_type = "[bold red]INJECTED[/bold red]" if s.is_injected else "Organic"
        cited_marker = (
            "[green]✓[/green]"
            if s.position in analysis.all_cited_sources
            else "[red]✗[/red]"
        )
        row_style = "on dark_green" if s.is_injected else None
        table.add_row(
            str(s.position),
            s.title[:40],
            s.url[:50],
            source_type,
            cited_marker,
            style=row_style,
        )
    console.print(table)

    # ── LLM response ────────────────────────────────────────────────────
    console.print("\n[bold]LLM Response:[/bold]")
    console.print(Panel(result.llm_response, border_style="green"))

    # ── Citation depth ────────────────────────────────────────────────
    console.print("\n[bold]Citation Depth (ranked by usage):[/bold]")
    depth_table = Table(show_header=True, header_style="bold magenta")
    depth_table.add_column("Rank", width=6, justify="center")
    depth_table.add_column("Source", width=10, justify="center")
    depth_table.add_column("Citations", width=10, justify="center")
    depth_table.add_column("Sentences", width=10, justify="center")
    depth_table.add_column("Type", width=10)

    for i, d in enumerate(analysis.citation_depth, start=1):
        is_ours = d.source_position == analysis.injected_source_position
        src_label = f"[Source {d.source_position}]"
        type_label = "[bold red]OURS[/bold red]" if is_ours else "Organic"
        row_style = "on dark_green" if is_ours else None
        depth_table.add_row(
            str(i),
            src_label,
            str(d.citation_count),
            str(d.sentences_attributed),
            type_label,
            style=row_style,
        )
    console.print(depth_table)

    # ── Citation analysis ────────────────────────────────────────────────
    console.print("\n[bold]Citation Analysis:[/bold]")

    def _yn(val: bool) -> str:
        return "[green]YES ✓[/green]" if val else "[red]NO ✗[/red]"

    console.print(
        f"  Site explicitly cited [Source #{analysis.injected_source_position}]: "
        f"{_yn(analysis.explicitly_cited)}"
    )
    if analysis.explicitly_cited:
        console.print(
            f"  Citation count: {analysis.injected_citation_count} "
            f"(rank #{analysis.injected_rank_by_depth} of "
            f"{len(analysis.citation_depth)} cited sources)"
        )
    console.print(f"  URL mentioned in response: {_yn(analysis.url_mentioned)}")
    console.print(f"  Domain mentioned in response: {_yn(analysis.domain_mentioned)}")
    console.print(
        f"  Content overlap phrases: {len(analysis.content_overlap_phrases)}"
    )
    console.print(
        f"  N-gram overlap: {analysis.ngram_overlap_count} "
        f"({analysis.ngram_overlap_ratio:.1%})"
    )
    console.print(f"  Sources cited: {len(analysis.all_cited_sources)}/{analysis.total_sources}")
    console.print(f"  All cited sources: {analysis.all_cited_sources}")

    # ── Verdict ──────────────────────────────────────────────────────────
    used = analysis.site_used_in_response
    colour = "green" if used else "red"
    verdict = (
        "✓ Your site WAS used in the LLM response"
        if used
        else "✗ Your site was NOT used in the LLM response"
    )
    console.print(
        Panel(
            f"[bold {colour}]{verdict}[/bold {colour}]",
            title="Verdict",
            border_style=colour,
        )
    )


def save_markdown_report(result: ExperimentResult, batch_dir=None) -> str:
    """Write a Markdown report file and return its path."""
    a = result.citation_analysis

    rows = ""
    for s in result.sources:
        s_type = "**INJECTED**" if s.is_injected else "Organic"
        cited = "✓" if s.position in a.all_cited_sources else "✗"
        rows += f"| {s.position} | {s.title[:50]} | {s.url} | {s_type} | {cited} |\n"

    # Citation depth table
    depth_rows = ""
    for i, d in enumerate(a.citation_depth, start=1):
        is_ours = d.source_position == a.injected_source_position
        label = "**OURS**" if is_ours else "Organic"
        depth_rows += (
            f"| {i} | [Source {d.source_position}] | "
            f"{d.citation_count} | {d.sentences_attributed} | {label} |\n"
        )

    overlap_section = ""
    if a.content_overlap_phrases:
        overlap_section = "\n## Content Overlap Details\n"
        for phrase in a.content_overlap_phrases:
            overlap_section += f'- "{phrase}"\n'

    md = f"""# GEO Experiment Report

| Field | Value |
|-------|-------|
| **Experiment ID** | {result.experiment_id} |
| **Date** | {result.timestamp} |
| **Model** | {result.model} |
| **Duration** | {result.duration_seconds}s |

## Query

> {result.query}

## Target Site

- **URL:** {result.site_url}
- **Injection Position:** Source #{a.injected_source_position} of {a.total_sources}

## Search Results & Sources

| # | Title | URL | Type | Cited? |
|---|-------|-----|------|--------|
{rows}

## LLM Response

{result.llm_response}

## Citation Depth (ranked by usage)

| Rank | Source | Citations | Sentences | Type |
|------|--------|-----------|-----------|------|
{depth_rows}

## Citation Analysis

| Metric | Result |
|--------|--------|
| Site explicitly cited | {"✓ YES" if a.explicitly_cited else "✗ NO"} |
| Citation count | {a.injected_citation_count} (rank #{a.injected_rank_by_depth} of {len(a.citation_depth)}) |
| URL mentioned | {"✓ YES" if a.url_mentioned else "✗ NO"} |
| Domain mentioned | {"✓ YES" if a.domain_mentioned else "✗ NO"} |
| Content overlap phrases | {len(a.content_overlap_phrases)} |
| N-gram overlap | {a.ngram_overlap_count} ({a.ngram_overlap_ratio:.1%}) |
| Sources cited | {len(a.all_cited_sources)}/{a.total_sources} |
| All cited sources | {a.all_cited_sources} |

## Verdict

**{"✓ Your site WAS used in the LLM response" if a.site_used_in_response else "✗ Your site was NOT used in the LLM response"}**
{overlap_section}"""

    from pathlib import Path
    out_dir = Path(batch_dir) if batch_dir else REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{result.experiment_id}.md"
    path.write_text(md)
    return str(path)
