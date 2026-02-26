"""Batch runner for GEO experiments against nutreeliya.com.

Usage:
  python run_batch.py <batch_name> <mode> <query_set>

  mode:       "control" (online site) or "experiment" (local site)
  query_set:  "set_a", "set_b", "set_c", "set_d"

Examples:
  python run_batch.py control_group control set_a
  python run_batch.py geo_v1 experiment set_b
"""

import sys
import time
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from geo_experiment.config import validate_config, REPORTS_DIR
from geo_experiment.experiment import run_experiment, ExperimentResult
from geo_experiment.report import save_markdown_report

console = Console()

SITE_URL = "https://nutreeliya.com"

# Control = online site content (never changes); Experiment = local site content (GEO optimized)
SITE_CONTENT_PATHS = {
    "control": Path("site_content/nutreeliya_homepage.txt"),
    "experiment": Path("site_content/nutreeliya_local_homepage.txt"),
}

# Query sets — rotate each batch to test general GEO, not query-specific
QUERY_SETS = {
    "set_a": [
        "best gluten-free recipes for celiac disease",
        "nutritious gluten-free dinner ideas with whole foods",
        "gluten-free quinoa buddha bowl recipe",
        "healthy gluten-free meal plan for better digestion",
        "easy gluten-free recipes that are actually delicious",
    ],
    "set_b": [
        "gluten-free recipes for beginners with simple ingredients",
        "best celiac-safe dinner recipes with high protein",
        "healthy gluten-free breakfast ideas for energy",
        "gluten-free Mediterranean diet recipes",
        "quick gluten-free lunch ideas for meal prep",
    ],
    "set_c": [
        "gluten-free comfort food recipes for winter",
        "best naturally gluten-free whole food meals",
        "gluten-free recipes with quinoa and vegetables",
        "celiac-friendly recipes that taste like regular food",
        "nutritious gluten-free recipes under 30 minutes",
    ],
    "set_d": [
        "gluten-free anti-inflammatory diet recipes",
        "best gluten-free recipes for gut health",
        "easy gluten-free family dinner ideas",
        "gluten-free baking without processed substitutes",
        "high-fiber gluten-free meals for digestive health",
    ],
}

INJECTION_RANK = 5            # Fixed at position 5 for scientific consistency
NUM_TAVILY_RESULTS = 10       # 10 organic + 1 injected = 11 total


def next_batch_number() -> int:
    """Find the next batch number by scanning existing batch folders."""
    existing = list(REPORTS_DIR.glob("batch_*"))
    if not existing:
        return 1
    nums = []
    for d in existing:
        try:
            nums.append(int(d.name.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return max(nums, default=0) + 1


def run_batch(
    batch_name: str,
    mode: str,
    query_set_name: str,
) -> tuple[list[ExperimentResult], Path]:
    validate_config()

    content_path = SITE_CONTENT_PATHS[mode]
    site_content = content_path.read_text()
    queries = QUERY_SETS[query_set_name]
    results: list[ExperimentResult] = []

    batch_num = next_batch_number()
    batch_dir = REPORTS_DIR / f"batch_{batch_num:03d}_{batch_name}"
    batch_dir.mkdir(parents=True, exist_ok=True)

    total = len(queries)
    site_label = "ONLINE (control)" if mode == "control" else "LOCAL (experiment)"

    console.print(
        Panel(
            f"[bold]GEO Batch Experiment[/bold]\n"
            f"Batch: {batch_dir.name}\n"
            f"Site: {SITE_URL} [{site_label}]\n"
            f"Content: {content_path.name}\n"
            f"Tavily results: {NUM_TAVILY_RESULTS} organic + 1 injected\n"
            f"Injection rank: {INJECTION_RANK}\n"
            f"Query set: {query_set_name} ({total} queries)\n"
            f"Total runs: {total}",
            border_style="blue",
        )
    )

    for run_num, query in enumerate(queries, start=1):
        console.print(
            f"\n[bold yellow]Run {run_num}/{total}[/bold yellow] "
            f'| Query: "{query[:50]}..."'
        )

        try:
            result = run_experiment(
                query=query,
                site_url=SITE_URL,
                site_content=site_content,
                injection_position=INJECTION_RANK,
                num_results=NUM_TAVILY_RESULTS,
                batch_dir=batch_dir,
            )
            results.append(result)

            a = result.citation_analysis
            cited = a.explicitly_cited
            used = a.site_used_in_response

            if cited:
                status = f"[green]CITED[/green] (×{a.injected_citation_count}, depth rank #{a.injected_rank_by_depth}/{len(a.citation_depth)})"
            elif used:
                status = "[yellow]USED (indirect)[/yellow]"
            else:
                status = "[red]NOT USED[/red]"

            console.print(
                f"  {status} | "
                f"Sources cited: {len(a.all_cited_sources)}/{a.total_sources} | "
                f"{result.duration_seconds}s"
            )

            save_markdown_report(result, batch_dir=batch_dir)

        except Exception as exc:
            console.print(f"  [red]ERROR: {exc}[/red]")

        time.sleep(2)

    return results, batch_dir


def write_summary(
    results: list[ExperimentResult],
    batch_dir: Path,
    batch_name: str,
    mode: str,
    query_set_name: str,
    queries: list[str],
) -> None:
    """Write summary to console and to summary.md in the batch folder."""

    cited_count = 0
    used_count = 0
    total_depth_ranks = []
    rows_md = ""

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("ID", width=22)
    table.add_column("Query", width=35)
    table.add_column("Inj. Pos", width=8, justify="center")
    table.add_column("Cited?", width=8, justify="center")
    table.add_column("Cite ×", width=7, justify="center")
    table.add_column("Depth Rank", width=11, justify="center")
    table.add_column("Cited/Total", width=12, justify="center")
    table.add_column("N-gram %", width=9, justify="center")

    for r in results:
        a = r.citation_analysis
        cited = a.explicitly_cited
        used = a.site_used_in_response

        if cited:
            cited_count += 1
            total_depth_ranks.append(a.injected_rank_by_depth)
        if used:
            used_count += 1

        cited_str = "[green]YES[/green]" if cited else "[red]NO[/red]"
        cite_count = str(a.injected_citation_count) if cited else "-"
        depth_rank = f"#{a.injected_rank_by_depth}/{len(a.citation_depth)}" if cited else "-"
        cited_total = f"{len(a.all_cited_sources)}/{a.total_sources}"

        table.add_row(
            r.experiment_id, r.query[:35], str(a.injected_source_position),
            cited_str, cite_count, depth_rank, cited_total,
            f"{a.ngram_overlap_ratio:.1%}",
        )

        cited_md = "YES" if cited else "NO"
        cite_count_md = str(a.injected_citation_count) if cited else "-"
        depth_rank_md = f"#{a.injected_rank_by_depth}/{len(a.citation_depth)}" if cited else "-"
        rows_md += (
            f"| {r.experiment_id} | {r.query[:40]} | {a.injected_source_position} | "
            f"{cited_md} | {cite_count_md} | {depth_rank_md} | "
            f"{len(a.all_cited_sources)}/{a.total_sources} | "
            f"{a.ngram_overlap_ratio:.1%} |\n"
        )

    total = len(results)
    avg_depth = sum(total_depth_ranks) / len(total_depth_ranks) if total_depth_ranks else 0
    site_label = "ONLINE (control)" if mode == "control" else "LOCAL (experiment)"

    # Console output
    console.print("\n")
    console.print(Panel(f"[bold]Batch Summary — {batch_dir.name}[/bold]", border_style="green"))
    console.print(table)
    console.print(f"\n[bold]Overall ({total} runs):[/bold]")
    if total:
        console.print(f"  Explicitly cited: {cited_count}/{total} ({cited_count/total:.0%})")
        console.print(f"  Used in response: {used_count}/{total} ({used_count/total:.0%})")
    if total_depth_ranks:
        console.print(f"  Avg depth rank when cited: #{avg_depth:.1f}")
    console.print(f"\n  Reports saved to: {batch_dir}")

    # Write summary.md
    summary_md = f"""# Batch Summary — {batch_dir.name}

| Field | Value |
|-------|-------|
| **Date** | {datetime.now().isoformat()} |
| **Batch** | {batch_name} |
| **Mode** | {site_label} |
| **Site URL** | {SITE_URL} |
| **Content file** | {SITE_CONTENT_PATHS[mode].name} |
| **Tavily results** | {NUM_TAVILY_RESULTS} organic + 1 injected |
| **Injection rank** | {INJECTION_RANK} |
| **Query set** | {query_set_name} |
| **Total runs** | {total} |

## Results

| ID | Query | Inj. Pos | Cited? | Cite x | Depth Rank | Cited/Total | N-gram % |
|----|-------|----------|--------|--------|------------|-------------|----------|
{rows_md}

## Overall

| Metric | Value |
|--------|-------|
| Explicitly cited | {cited_count}/{total} ({cited_count/total:.0%}) |
| Used in response | {used_count}/{total} ({used_count/total:.0%}) |
| Avg depth rank when cited | {'#' + f'{avg_depth:.1f}' if total_depth_ranks else 'N/A'} |

## Queries Used ({query_set_name})

{chr(10).join(f'{i+1}. "{q}"' for i, q in enumerate(queries))}
"""

    (batch_dir / "summary.md").write_text(summary_md)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        console.print(
            "[bold red]Usage:[/bold red] python run_batch.py <batch_name> <control|experiment> <set_a|set_b|set_c|set_d>"
        )
        sys.exit(1)

    batch_name = sys.argv[1]
    mode = sys.argv[2]
    query_set_name = sys.argv[3]

    if mode not in SITE_CONTENT_PATHS:
        console.print(f"[red]Invalid mode '{mode}'. Use 'control' or 'experiment'.[/red]")
        sys.exit(1)
    if query_set_name not in QUERY_SETS:
        console.print(f"[red]Invalid query set '{query_set_name}'. Use: {', '.join(QUERY_SETS.keys())}[/red]")
        sys.exit(1)

    queries = QUERY_SETS[query_set_name]
    results, batch_dir = run_batch(batch_name, mode, query_set_name)
    write_summary(results, batch_dir, batch_name, mode, query_set_name, queries)
