"""Content Decay Dashboard — CLI entry point.

Usage:
    python dashboard.py [options]

Options:
    --property URL    GSC property URL (overrides .env)
    --days N          Days per comparison window (default: 90 ≈ 3 months)
    --min-clicks N    Min clicks to include a URL (default: 5)
    --top N           Max rows to display (default: 50)
    --no-titles       Skip fetching page titles (faster)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

load_dotenv()

console = Console(stderr=True)
out = Console()  # stdout for the table


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dashboard.py",
        description="Detect content decay in Google Search Console data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--property",
        default=os.getenv("GSC_PROPERTY_URL"),
        metavar="URL",
        help=(
            "GSC property URL, e.g. 'sc-domain:example.com' or "
            "'https://www.example.com/'. Defaults to GSC_PROPERTY_URL in .env."
        ),
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        metavar="N",
        help="Number of days in each comparison window (default: 90 ≈ 3 months).",
    )
    parser.add_argument(
        "--min-clicks",
        type=int,
        default=5,
        metavar="N",
        help="Minimum click count to include a URL (default: 5).",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        metavar="N",
        help="Maximum number of decaying pages to display (default: 50).",
    )
    parser.add_argument(
        "--no-titles",
        action="store_true",
        help="Skip fetching page titles (faster run, URL-only display).",
    )
    return parser


def _spinner(description: str):
    """Return a transient Rich Progress spinner context manager."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    )


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    if not args.property:
        console.print(
            "[bold red]Error:[/bold red] GSC property URL is required.\n"
            "Set [bold]GSC_PROPERTY_URL[/bold] in your [bold].env[/bold] file "
            "or pass [bold]--property[/bold] on the command line."
        )
        sys.exit(1)

    credentials_path = os.getenv("CREDENTIALS_PATH", "credentials.json")

    # GSC data has a ~3-day processing lag
    today = date.today()
    recent_end = today - timedelta(days=3)
    recent_start = recent_end - timedelta(days=args.days - 1)
    prior_end = recent_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=args.days - 1)

    # ------------------------------------------------------------------
    # Authenticate
    # ------------------------------------------------------------------
    with _spinner("Authenticating with Google…") as p:
        p.add_task("Authenticating with Google…")
        from src.auth import get_credentials
        try:
            creds = get_credentials(credentials_path)
        except FileNotFoundError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            sys.exit(1)

    console.print("[green]✓[/green] Authenticated")

    # ------------------------------------------------------------------
    # Fetch GSC data
    # ------------------------------------------------------------------
    from src.gsc_client import GSCClient

    client = GSCClient(creds, args.property)

    with _spinner("Fetching page-level data…") as p:
        p.add_task("Fetching page-level data…")
        recent_pages = client.get_page_data(recent_start, recent_end)

    console.print(f"[green]✓[/green] Page data loaded  [dim]({len(recent_pages):,} pages in recent period)[/dim]")

    with _spinner("Fetching prior period page data…") as p:
        p.add_task("Fetching prior period page data…")
        prior_pages = client.get_page_data(prior_start, prior_end)

    console.print(f"[green]✓[/green] Prior period loaded  [dim]({len(prior_pages):,} pages)[/dim]")

    with _spinner("Fetching keyword-level data (recent)…") as p:
        p.add_task("Fetching keyword-level data (recent)…")
        recent_keywords = client.get_keyword_data(recent_start, recent_end)

    console.print(f"[green]✓[/green] Recent keywords loaded  [dim]({len(recent_keywords):,} pages with keyword data)[/dim]")

    with _spinner("Fetching keyword-level data (prior)…") as p:
        p.add_task("Fetching keyword-level data (prior)…")
        prior_keywords = client.get_keyword_data(prior_start, prior_end)

    console.print(f"[green]✓[/green] Prior keywords loaded  [dim]({len(prior_keywords):,} pages)[/dim]")

    # ------------------------------------------------------------------
    # Analyse
    # ------------------------------------------------------------------
    with _spinner("Analysing decay signals…") as p:
        p.add_task("Analysing decay signals…")
        from src.analyzer import analyze_decay
        results = analyze_decay(
            recent_pages,
            prior_pages,
            recent_keywords,
            prior_keywords,
            min_clicks=args.min_clicks,
        )

    console.print(f"[green]✓[/green] Analysis complete  [dim]({len(results)} decaying pages found)[/dim]")

    # ------------------------------------------------------------------
    # Fetch page titles
    # ------------------------------------------------------------------
    titles: dict[str, str] = {}
    if results and not args.no_titles:
        from src.title_fetcher import fetch_titles
        urls = [r.url for r in results[: args.top]]
        console.print(f"[dim]Fetching titles for {len(urls)} URLs…[/dim]")
        titles = fetch_titles(urls, console)
        console.print(f"[green]✓[/green] Titles fetched")

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    from src.display import display_decay_table

    display_decay_table(
        results,
        recent_start=recent_start,
        recent_end=recent_end,
        prior_start=prior_start,
        prior_end=prior_end,
        titles=titles,
        top_n=args.top,
        property_url=args.property,
    )


if __name__ == "__main__":
    main()
