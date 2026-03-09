"""Content Decay Dashboard — CLI entry point.

Usage:
    python dashboard.py [options]

Options:
    --property URL    GSC property URL (overrides .env)
    --days N          Days per comparison window (default: 90 ≈ 3 months)
    --min-clicks N    Min clicks to include a URL (default: 5)
    --top N           Max rows to display (default: 50)
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console(stderr=True)


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
            "'https://example.com/'.  Defaults to GSC_PROPERTY_URL in .env."
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
    return parser


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

    # GSC data has a ~3-day processing lag; account for that
    today = date.today()
    recent_end = today - timedelta(days=3)
    recent_start = recent_end - timedelta(days=args.days - 1)
    prior_end = recent_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=args.days - 1)

    console.print(
        f"\n[bold cyan]Content Decay Dashboard[/bold cyan]\n"
        f"Property : [bold]{args.property}[/bold]\n"
        f"Recent   : {recent_start} → {recent_end}  ({args.days} days)\n"
        f"Prior    : {prior_start} → {prior_end}  ({args.days} days)\n"
    )

    # --- Authentication ---
    console.print("[dim]Authenticating with Google…[/dim]")
    from src.auth import get_credentials  # noqa: PLC0415

    try:
        creds = get_credentials(credentials_path)
    except FileNotFoundError as exc:
        console.print(f"[bold red]Error:[/bold red] {exc}")
        sys.exit(1)

    # --- Fetch data ---
    from src.gsc_client import GSCClient  # noqa: PLC0415

    client = GSCClient(creds, args.property)

    console.print("[dim]Fetching page-level data…[/dim]")
    recent_pages = client.get_page_data(recent_start, recent_end)
    prior_pages = client.get_page_data(prior_start, prior_end)

    console.print("[dim]Fetching keyword-level data…[/dim]")
    recent_keywords = client.get_keyword_data(recent_start, recent_end)
    prior_keywords = client.get_keyword_data(prior_start, prior_end)

    console.print(
        f"[dim]Loaded {len(recent_pages):,} pages (recent) / "
        f"{len(prior_pages):,} pages (prior)[/dim]\n"
    )

    # --- Analyse ---
    from src.analyzer import analyze_decay  # noqa: PLC0415

    results = analyze_decay(
        recent_pages,
        prior_pages,
        recent_keywords,
        prior_keywords,
        min_clicks=args.min_clicks,
    )

    # --- Display ---
    from src.display import display_decay_table  # noqa: PLC0415

    display_decay_table(
        results,
        recent_start=recent_start,
        recent_end=recent_end,
        prior_start=prior_start,
        prior_end=prior_end,
        top_n=args.top,
    )


if __name__ == "__main__":
    main()
