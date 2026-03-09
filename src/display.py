"""Rich terminal display for the content decay dashboard."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from rich.text import Text

from .analyzer import DecayResult

console = Console()


# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _severity_color(score: float) -> str:
    if score >= 60:
        return "bold red"
    if score >= 35:
        return "bold yellow"
    return "yellow"


def _change_color(value: float, *, invert: bool = False) -> str:
    """Return a Rich style string for a numeric change value.

    Args:
        value:  The delta (positive or negative).
        invert: If True, positive values are bad (e.g. position drop).
    """
    if invert:
        if value > 0:
            return "red"
        if value < 0:
            return "green"
    else:
        if value < 0:
            return "red"
        if value > 0:
            return "green"
    return "white"


def _fmt_pct(value: float, *, sign: bool = True, invert: bool = False) -> Text:
    color = _change_color(value, invert=invert)
    prefix = "+" if (sign and value > 0) else ""
    return Text(f"{prefix}{value:.1f}%", style=color)


def _fmt_pos_change(change: float) -> Text:
    color = _change_color(change, invert=True)
    prefix = "+" if change > 0 else ""
    arrow = "▲" if change > 0 else ("▼" if change < 0 else "")
    return Text(f"{arrow}{prefix}{change:+.1f}", style=color)


def _severity_bar(score: float) -> Text:
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    color = _severity_color(score)
    return Text(f"{bar} {score:.0f}", style=color)


def _truncate_url(url: str, max_len: int = 55) -> str:
    if len(url) <= max_len:
        return url
    # Keep the path, trim the middle
    return url[: max_len - 3] + "…"


# ---------------------------------------------------------------------------
# Main display function
# ---------------------------------------------------------------------------

def display_decay_table(
    results: Sequence[DecayResult],
    recent_start: date,
    recent_end: date,
    prior_start: date,
    prior_end: date,
    top_n: int = 50,
) -> None:
    """Render the full content decay report to the terminal."""

    # --- Header panel ---
    header_lines = [
        f"[bold white]Recent period:[/bold white]  {recent_start} → {recent_end}",
        f"[bold white]Prior period:[/bold white]   {prior_start} → {prior_end}",
        f"[bold white]Decaying URLs found:[/bold white] {len(results)}",
    ]
    console.print(
        Panel(
            "\n".join(header_lines),
            title="[bold cyan] Content Decay Dashboard[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not results:
        console.print(
            "\n[bold green]No content decay detected.[/bold green] "
            "All tracked pages are stable or improving.\n"
        )
        return

    display = list(results[:top_n])

    # --- Main table ---
    table = Table(
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold cyan",
        show_lines=True,
        expand=True,
        title=f"[bold]Top {len(display)} Decaying Pages[/bold] (sorted by severity)",
        title_style="bold white",
    )

    table.add_column("#", style="dim", width=4, justify="right")
    table.add_column("URL", min_width=35, no_wrap=False)
    table.add_column("Pos\nBefore", justify="right", width=7)
    table.add_column("Pos\nNow", justify="right", width=7)
    table.add_column("Pos\nΔ", justify="right", width=7)
    table.add_column("CTR\nBefore", justify="right", width=8)
    table.add_column("CTR\nNow", justify="right", width=8)
    table.add_column("CTR Δ%", justify="right", width=8)
    table.add_column("Clicks\nBefore", justify="right", width=8)
    table.add_column("Clicks\nNow", justify="right", width=8)
    table.add_column("Clicks Δ%", justify="right", width=10)
    table.add_column("P1 Kws\nLost", justify="right", width=9)
    table.add_column("Severity", width=20)
    table.add_column("Flags", min_width=20)

    for idx, r in enumerate(display, start=1):
        ctr_change_pct = (
            (r.ctr_change / r.prior_ctr * 100) if r.prior_ctr else 0.0
        )
        p1_loss_text = (
            Text(str(r.page1_kw_loss), style="red bold")
            if r.page1_kw_loss > 0
            else Text("0", style="dim")
        )
        flags_text = Text(", ".join(r.flags) if r.flags else "—", style="dim")

        table.add_row(
            str(idx),
            _truncate_url(r.url),
            f"{r.prior_position:.1f}",
            Text(f"{r.recent_position:.1f}", style=_change_color(r.position_change, invert=True)),
            _fmt_pos_change(r.position_change),
            f"{r.prior_ctr * 100:.2f}%",
            Text(f"{r.recent_ctr * 100:.2f}%", style=_change_color(r.ctr_change)),
            _fmt_pct(ctr_change_pct, invert=False) if r.ctr_change < 0 else Text(f"+{ctr_change_pct:.1f}%", style="green"),
            f"{r.prior_clicks:.0f}",
            Text(f"{r.recent_clicks:.0f}", style=_change_color(r.click_change)),
            _fmt_pct(r.click_change_pct),
            p1_loss_text,
            _severity_bar(r.severity),
            flags_text,
        )

    console.print(table)

    # --- Summary stats ---
    avg_pos_drop = sum(r.position_change for r in results if r.position_change > 0) / max(
        sum(1 for r in results if r.position_change > 0), 1
    )
    total_click_loss = sum(r.click_change for r in results if r.click_change < 0)
    fell_off_page1 = sum(
        1 for r in results if r.prior_position <= 10 and r.recent_position > 10
    )

    console.print(
        Panel(
            f"[bold]Avg position drop (decaying pages):[/bold] {avg_pos_drop:.1f}\n"
            f"[bold]Total click loss:[/bold] {total_click_loss:,.0f}\n"
            f"[bold]Pages that fell off page 1:[/bold] {fell_off_page1}",
            title="[bold cyan]Summary[/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )
