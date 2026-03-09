"""Content decay analysis: compare two GSC periods and score each URL."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DecayResult:
    """Holds decay metrics and a composite severity score for one URL."""

    url: str

    # --- Page-level metrics ---
    prior_clicks: float = 0.0
    recent_clicks: float = 0.0
    prior_impressions: float = 0.0
    recent_impressions: float = 0.0
    prior_position: float = 0.0
    recent_position: float = 0.0
    prior_ctr: float = 0.0
    recent_ctr: float = 0.0

    # --- Derived changes ---
    click_change: float = 0.0          # recent - prior (negative = loss)
    click_change_pct: float = 0.0      # % change
    impression_change: float = 0.0
    impression_change_pct: float = 0.0
    position_change: float = 0.0       # positive = dropped (worse)
    ctr_change: float = 0.0            # negative = declined

    # --- Keyword-level ---
    prior_page1_kws: int = 0           # keywords at position ≤ 10 in prior period
    recent_page1_kws: int = 0
    page1_kw_loss: int = 0             # prior_page1_kws - recent_page1_kws
    page1_kw_loss_pct: float = 0.0

    # --- Composite score 0–100 (higher = more severe decay) ---
    severity: float = 0.0

    # --- Decay flags (human-readable reasons) ---
    flags: list[str] = field(default_factory=list)


def analyze_decay(
    recent_pages: dict[str, dict[str, Any]],
    prior_pages: dict[str, dict[str, Any]],
    recent_keywords: dict[str, list[dict[str, Any]]],
    prior_keywords: dict[str, list[dict[str, Any]]],
    min_clicks: int = 5,
) -> list[DecayResult]:
    """Compare two periods and return URLs exhibiting content decay.

    A URL is considered *decaying* if it satisfies at least one:
    - Position dropped by ≥ 2
    - CTR declined by ≥ 10 %
    - Clicks declined by ≥ 15 %
    - At least one page-1 keyword fell off page 1

    Only URLs with ``max(prior_clicks, recent_clicks) >= min_clicks`` are
    included to filter statistical noise.

    Args:
        recent_pages:    URL → metrics dict for the recent period.
        prior_pages:     URL → metrics dict for the prior period.
        recent_keywords: URL → list of keyword dicts for the recent period.
        prior_keywords:  URL → list of keyword dicts for the prior period.
        min_clicks:      Minimum clicks threshold for inclusion.

    Returns:
        List of :class:`DecayResult` objects sorted by severity descending.
    """
    results: list[DecayResult] = []

    # Only analyse URLs that existed in the prior period so we see real decay
    for url, prior in prior_pages.items():
        recent = recent_pages.get(url)

        prior_clicks = prior["clicks"]
        recent_clicks = recent["clicks"] if recent else 0.0

        # Skip low-traffic noise
        if max(prior_clicks, recent_clicks) < min_clicks:
            continue

        result = DecayResult(url=url)

        # --- Page metrics ---
        result.prior_clicks = prior_clicks
        result.recent_clicks = recent_clicks
        result.prior_impressions = prior["impressions"]
        result.recent_impressions = recent["impressions"] if recent else 0.0
        result.prior_position = prior["position"]
        result.recent_position = recent["position"] if recent else 100.0
        result.prior_ctr = prior["ctr"]
        result.recent_ctr = recent["ctr"] if recent else 0.0

        # --- Derived changes ---
        result.click_change = result.recent_clicks - result.prior_clicks
        result.click_change_pct = (
            (result.click_change / result.prior_clicks * 100)
            if result.prior_clicks
            else 0.0
        )
        result.impression_change = result.recent_impressions - result.prior_impressions
        result.impression_change_pct = (
            (result.impression_change / result.prior_impressions * 100)
            if result.prior_impressions
            else 0.0
        )
        result.position_change = result.recent_position - result.prior_position
        result.ctr_change = result.recent_ctr - result.prior_ctr

        # --- Keyword page-1 analysis ---
        prior_kws = {kw["query"]: kw for kw in prior_keywords.get(url, [])}
        recent_kws = {kw["query"]: kw for kw in recent_keywords.get(url, [])}

        result.prior_page1_kws = sum(
            1 for kw in prior_kws.values() if kw["position"] <= 10
        )
        result.recent_page1_kws = sum(
            1 for kw in recent_kws.values() if kw["position"] <= 10
        )
        result.page1_kw_loss = max(
            0, result.prior_page1_kws - result.recent_page1_kws
        )
        result.page1_kw_loss_pct = (
            (result.page1_kw_loss / result.prior_page1_kws * 100)
            if result.prior_page1_kws
            else 0.0
        )

        # --- Severity score (0–100) ---
        score = 0.0

        # Position drop (0–30 pts)
        if result.position_change >= 10:
            score += 30
            result.flags.append("severe position drop")
        elif result.position_change >= 5:
            score += 20
            result.flags.append("notable position drop")
        elif result.position_change >= 2:
            score += 10
            result.flags.append("position drop")

        # Fell off page 1 entirely (bonus 10 pts if currently > 10)
        if result.prior_position <= 10 and result.recent_position > 10:
            score += 10
            result.flags.append("fell off page 1")

        # Page-1 keyword loss (0–30 pts)
        if result.page1_kw_loss_pct >= 50:
            score += 30
            result.flags.append(f"{result.page1_kw_loss} page-1 kw(s) lost")
        elif result.page1_kw_loss_pct >= 25:
            score += 20
            result.flags.append(f"{result.page1_kw_loss} page-1 kw(s) lost")
        elif result.page1_kw_loss > 0:
            score += 10
            result.flags.append(f"{result.page1_kw_loss} page-1 kw(s) lost")

        # CTR decline (0–20 pts)
        ctr_decline_pct = (
            (abs(result.ctr_change) / result.prior_ctr * 100)
            if result.prior_ctr
            else 0.0
        )
        if result.ctr_change < 0:
            if ctr_decline_pct >= 50:
                score += 20
                result.flags.append("severe CTR decline")
            elif ctr_decline_pct >= 25:
                score += 12
                result.flags.append("CTR decline")
            elif ctr_decline_pct >= 10:
                score += 6
                result.flags.append("CTR decline")

        # Click loss (0–20 pts)
        if result.click_change_pct <= -50:
            score += 20
            result.flags.append("severe click loss")
        elif result.click_change_pct <= -30:
            score += 13
            result.flags.append("click loss")
        elif result.click_change_pct <= -15:
            score += 7
            result.flags.append("click loss")

        result.severity = min(round(score, 1), 100.0)

        # Only surface pages with actual decay signals
        ctr_decline_relative = (
            abs(result.ctr_change) / result.prior_ctr
            if result.prior_ctr
            else 0.0
        )
        is_decaying = (
            result.position_change >= 2
            or (result.ctr_change < 0 and ctr_decline_relative >= 0.10)
            or result.click_change_pct <= -15
            or result.page1_kw_loss > 0
        )
        if is_decaying and result.severity > 0:
            results.append(result)

    results.sort(key=lambda r: r.severity, reverse=True)
    return results
