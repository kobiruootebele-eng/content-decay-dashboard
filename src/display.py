"""Rich terminal display for the Content Decay Dashboard."""

from __future__ import annotations

from datetime import date
from typing import Sequence

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from .analyzer import DecayResult

console = Console()


# ---------------------------------------------------------------------------
# Severity thresholds
# ---------------------------------------------------------------------------
_CRITICAL = 60
_WARNING = 35


def _severity_label(score: float) -> tuple[str, str]:
    """Return (label, Rich style) based on score."""
    if score >= _CRITICAL:
        return "CRITICAL", "bold red"
    if score >= _WARNING:
        return "WARNING", "bold yellow"
    return "MILD", "dim yellow"


def _row_style(score: float) -> str:
    if score >= _CRITICAL:
        return "red"
    if score >= _WARNING:
        return "yellow"
    return ""


# ---------------------------------------------------------------------------
# Cell builders
# ---------------------------------------------------------------------------

def _pos_cell(before: float, now: float) -> Text:
    delta = now - before
    t = Text()
    t.append(f"{before:.1f}", style="dim")
    t.append(" → ")
    t.append(f"{now:.1f}", style="bold")
    if delta > 0:
        t.append(f"  ▲+{delta:.1f}", style="red")
    elif delta < 0:
        t.append(f"  ▼{delta:.1f}", style="green")
    else:
        t.append("  —", style="dim")
    return t


def _pct_cell(before: float, now: float, *, fmt: str = ".2f", suffix: str = "") -> Text:
    """Generic before→now cell with coloured delta."""
    delta = now - before
    delta_pct = (delta / before * 100) if before else 0.0
    t = Text()
    t.append(f"{before:{fmt}}{suffix}", style="dim")
    t.append(" → ")
    t.append(f"{now:{fmt}}{suffix}", style="bold")
    if delta < 0:
        t.append(f"  ({delta_pct:+.1f}%)", style="red")
    elif delta > 0:
        t.append(f"  ({delta_pct:+.1f}%)", style="green")
    else:
        t.append("  (—)", style="dim")
    return t


def _clicks_cell(before: float, now: float) -> Text:
    delta = now - before
    delta_pct = (delta / before * 100) if before else 0.0
    t = Text()
    t.append(f"{before:,.0f}", style="dim")
    t.append(" → ")
    t.append(f"{now:,.0f}", style="bold")
    if delta < 0:
        t.append(f"  ({delta_pct:+.1f}%)", style="red")
    elif delta > 0:
        t.append(f"  ({delta_pct:+.1f}%)", style="green")
    else:
        t.append("  (—)", style="dim")
    return t


def _severity_bar(score: float) -> Text:
    filled = int(score / 10)
    bar = "█" * filled + "░" * (10 - filled)
    label, style = _severity_label(score)
    t = Text()
    t.append(bar, style=style)
    t.append(f"  {score:.0f}  ", style="dim")
    t.append(label, style=style)
    return t


def _title_cell(title: str, url: str, max_title: int = 48, max_url: int = 52) -> Text:
    t = Text()
    display_title = (title[:max_title] + "…") if len(title) > max_title else title
    display_url = (url[:max_url] + "…") if len(url) > max_url else url
    if display_title:
        t.append(display_title + "\n", style="bold white")
    t.append(display_url, style="dim cyan")
    return t


def _kw_loss_cell(lost: int, pct: float) -> Text:
    if lost == 0:
        return Text("—", style="dim")
    t = Text()
    t.append(f"{lost}", style="bold red")
    if pct:
        t.append(f"  ({pct:.0f}%)", style="red")
    return t


# ---------------------------------------------------------------------------
# Main display function
# ---------------------------------------------------------------------------

def display_decay_table(
    results: Sequence[DecayResult],
    recent_start: date,
    recent_end: date,
    prior_start: date,
    prior_end: date,
    titles: dict[str, str] | None = None,
    top_n: int = 50,
    property_url: str = "",
) -> None:
    """Render the full content decay report to stdout."""

    titles = titles or {}
    days = (recent_end - recent_start).days + 1
    critical = [r for r in results if r.severity >= _CRITICAL]
    warning = [r for r in results if _WARNING <= r.severity < _CRITICAL]
    mild = [r for r in results if r.severity < _WARNING]

    # ------------------------------------------------------------------
    # Header panel
    # ------------------------------------------------------------------
    header = Text()
    if property_url:
        header.append(f"  Property   ", style="dim")
        header.append(f"{property_url}\n", style="bold cyan")
    header.append(f"  Recent     ", style="dim")
    header.append(f"{recent_start}  →  {recent_end}", style="white")
    header.append(f"  ({days} days)\n", style="dim")
    header.append(f"  Prior      ", style="dim")
    header.append(f"{prior_start}  →  {prior_end}", style="white")
    header.append(f"  ({days} days)\n\n", style="dim")

    if not results:
        header.append("  ✓ No content decay detected — all pages are stable or improving.", style="bold green")
    else:
        header.append(f"  Decaying pages found:  ", style="dim")
        header.append(f"{len(results)}\n", style="bold white")
        header.append(f"  ", style="")
        header.append(f"● {len(critical)} Critical  ", style="bold red")
        header.append(f"● {len(warning)} Warning  ", style="bold yellow")
        header.append(f"● {len(mild)} Mild", style="dim yellow")

    console.print()
    console.print(
        Panel(
            header,
            title="[bold cyan] Content Decay Dashboard [/bold cyan]",
            border_style="cyan",
            padding=(1, 2),
        )
    )

    if not results:
        return

    # ------------------------------------------------------------------
    # Main table
    # ------------------------------------------------------------------
    display = list(results[:top_n])

    table = Table(
        box=box.ROUNDED,
        border_style="dim",
        header_style="bold cyan",
        show_lines=True,
        expand=True,
        title=f"[bold white]Top {len(display)} Decaying Pages[/bold white]"
        f"[dim]  —  sorted by severity[/dim]",
        title_style="",
        caption="[dim]▲ = position worsened (higher number)   ▼ = position improved[/dim]",
    )

    table.add_column("#", width=3, justify="right", style="dim")
    table.add_column("Article / URL", min_width=40, no_wrap=False)
    table.add_column("Position\nbefore → now (Δ)", min_width=22, justify="left")
    table.add_column("CTR\nbefore → now (Δ%)", min_width=22, justify="left")
    table.add_column("Clicks\nbefore → now (Δ%)", min_width=22, justify="left")
    table.add_column("Page-1\nKws Lost", width=12, justify="center")
    table.add_column("Severity", min_width=26, justify="left")
    table.add_column("Signals", min_width=24, no_wrap=False)

    for idx, r in enumerate(display, start=1):
        title = titles.get(r.url, "")
        flags_text = Text(", ".join(r.flags) if r.flags else "—", style="dim")

        table.add_row(
            str(idx),
            _title_cell(title, r.url),
            _pos_cell(r.prior_position, r.recent_position),
            _pct_cell(r.prior_ctr * 100, r.recent_ctr * 100, fmt=".2f", suffix="%"),
            _clicks_cell(r.prior_clicks, r.recent_clicks),
            _kw_loss_cell(r.page1_kw_loss, r.page1_kw_loss_pct),
            _severity_bar(r.severity),
            flags_text,
            style=_row_style(r.severity),
        )

    console.print(table)

    # ------------------------------------------------------------------
    # Summary panel
    # ------------------------------------------------------------------
    avg_pos_drop = (
        sum(r.position_change for r in results if r.position_change > 0)
        / max(sum(1 for r in results if r.position_change > 0), 1)
    )
    total_click_loss = sum(r.click_change for r in results if r.click_change < 0)
    fell_off_p1 = sum(
        1 for r in results if r.prior_position <= 10 and r.recent_position > 10
    )
    total_kw_loss = sum(r.page1_kw_loss for r in results)

    left = Text()
    left.append("Severity breakdown\n\n", style="bold white")
    left.append("● Critical  (≥60)  ", style="bold red")
    left.append(f"{len(critical)} pages\n", style="bold white")
    left.append("● Warning   (≥35)  ", style="bold yellow")
    left.append(f"{len(warning)} pages\n", style="bold white")
    left.append("● Mild      (<35)  ", style="dim yellow")
    left.append(f"{len(mild)} pages", style="bold white")

    right = Text()
    right.append("Key metrics\n\n", style="bold white")
    right.append("Avg position drop       ", style="dim")
    right.append(f"{avg_pos_drop:+.1f}\n", style="red" if avg_pos_drop > 0 else "green")
    right.append("Total click loss        ", style="dim")
    right.append(f"{total_click_loss:,.0f}\n", style="red")
    right.append("Pages fell off page 1   ", style="dim")
    right.append(f"{fell_off_p1}\n", style="red" if fell_off_p1 else "white")
    right.append("Total page-1 kw lost    ", style="dim")
    right.append(f"{total_kw_loss}", style="red" if total_kw_loss else "white")

    console.print(
        Panel(
            Columns([left, right], expand=True, padding=(0, 6)),
            title="[bold cyan] Summary [/bold cyan]",
            border_style="cyan",
            padding=(1, 3),
        )
    )
    console.print()
