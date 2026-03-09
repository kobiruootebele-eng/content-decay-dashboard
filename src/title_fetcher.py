"""Fetch HTML page titles for decaying URLs via parallel HTTP requests."""

from __future__ import annotations

import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_TIMEOUT = 6        # seconds per request
_MAX_WORKERS = 15   # parallel fetches
_MAX_BYTES = 8192   # read first 8 KB only — enough to find <title>
_HTML_ENTITIES = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">",
    "&#39;": "'", "&quot;": '"', "&nbsp;": " ",
}


def _fetch_title(url: str) -> tuple[str, str]:
    """Return (url, title). Falls back to empty string on any error."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ContentDecayBot/1.0)"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.read(_MAX_BYTES).decode("utf-8", errors="replace")

        match = _TITLE_RE.search(raw)
        if match:
            title = re.sub(r"\s+", " ", match.group(1).strip())
            for entity, char in _HTML_ENTITIES.items():
                title = title.replace(entity, char)
            return url, title
    except Exception:
        pass
    return url, ""


def fetch_titles(urls: list[str], console: Console) -> dict[str, str]:
    """Fetch page titles for a list of URLs in parallel.

    Args:
        urls:    List of page URLs to fetch titles for.
        console: Rich Console to render the progress bar on.

    Returns:
        Mapping of ``url -> title`` (empty string if unreachable).
    """
    titles: dict[str, str] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Fetching page titles…", total=len(urls))
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
            futures = {executor.submit(_fetch_title, url): url for url in urls}
            for future in as_completed(futures):
                url, title = future.result()
                titles[url] = title
                progress.advance(task)

    return titles
