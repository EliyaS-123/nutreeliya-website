"""CLI entry-point for the GEO Poisoning Experiment.

Two modes:
  python main.py chat        — Interactive agent backed by Azure OpenAI + Tavily
  python main.py experiment  — Controlled GEO experiment with citation analysis
"""

import argparse
import os
import sys

from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.panel import Panel

console = Console()


# ── Chat mode ────────────────────────────────────────────────────────────────


def run_chat() -> None:
    from geo_experiment.config import validate_config
    from geo_experiment.agent import create_geo_agent, chat

    validate_config()

    console.print(
        Panel(
            "[bold]GEO Research Agent[/bold]\nType 'quit' to exit.",
            border_style="blue",
        )
    )

    with console.status("Initializing agent…"):
        agent = create_geo_agent(verbose=True)

    console.print("[green]Agent ready![/green]\n")

    while True:
        try:
            query = Prompt.ask("\n[bold cyan]You[/bold cyan]")
        except (KeyboardInterrupt, EOFError):
            break

        if query.strip().lower() in ("quit", "exit", "q"):
            break
        if not query.strip():
            continue

        try:
            response = chat(agent, query)
            console.print(f"\n[bold green]Agent:[/bold green] {response}")
        except Exception as exc:
            console.print(f"[red]Error: {exc}[/red]")


# ── Experiment mode ──────────────────────────────────────────────────────────


def run_experiment_mode(args: argparse.Namespace) -> None:
    from geo_experiment.config import validate_config
    from geo_experiment.experiment import run_experiment
    from geo_experiment.report import print_report, save_markdown_report

    validate_config()

    console.print(
        Panel(
            "[bold]GEO Experiment Runner[/bold]\n"
            "Test whether an LLM selects your site from retrieved web sources.",
            border_style="blue",
        )
    )

    query = Prompt.ask("\n[bold]Search query[/bold]")
    site_url = Prompt.ask("[bold]Your site URL[/bold]")

    console.print(
        "[dim]Enter site content below (paste text, or provide a path to a .txt file):[/dim]"
    )
    content_input = Prompt.ask("[bold]Site content[/bold]")

    if os.path.isfile(content_input):
        with open(content_input) as f:
            site_content = f.read()
        console.print(f"[dim]Loaded {len(site_content)} chars from {content_input}[/dim]")
    else:
        site_content = content_input

    # Use CLI flag if provided, otherwise prompt interactively
    if args.injection_rank is not None:
        injection_pos = args.injection_rank
        console.print(f"[dim]Injection rank (from CLI): {injection_pos}[/dim]")
    else:
        injection_pos = IntPrompt.ask(
            "[bold]Injection position[/bold] (0 = first, among N search results)",
            default=3,
        )

    num_results = IntPrompt.ask(
        "[bold]Number of Tavily results to fetch[/bold]",
        default=10,
    )

    console.print()
    with console.status("[bold]Running experiment…[/bold]"):
        result = run_experiment(
            query=query,
            site_url=site_url,
            site_content=site_content,
            injection_position=injection_pos,
            num_results=num_results,
        )

    print_report(result)
    md_path = save_markdown_report(result)

    console.print(f"\n[dim]Markdown report → {md_path}[/dim]")
    console.print(f"[dim]JSON data       → reports/{result.experiment_id}.json[/dim]")


# ── Entrypoint ───────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="GEO Poisoning Experiment — Measure LLM source selection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "mode",
        choices=["chat", "experiment"],
        help="'chat' for interactive agent, 'experiment' for controlled GEO test",
    )
    parser.add_argument(
        "--injection-rank",
        type=int,
        default=None,
        metavar="N",
        help="Position to inject your site among Tavily results (0 = first). "
             "If omitted, you will be prompted interactively.",
    )
    args = parser.parse_args()

    if args.mode == "chat":
        run_chat()
    else:
        run_experiment_mode(args)


if __name__ == "__main__":
    main()
