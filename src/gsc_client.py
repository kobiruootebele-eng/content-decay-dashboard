"""Google Search Console API client."""

from __future__ import annotations

import time
from datetime import date
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from rich.console import Console

console = Console(stderr=True)

# GSC allows up to 25 000 rows per request
_MAX_ROWS = 25_000
# Polite retry delay on quota errors (seconds)
_RETRY_DELAY = 5


class GSCClient:
    """Thin wrapper around the Search Console searchanalytics API."""

    def __init__(self, credentials: Credentials, property_url: str) -> None:
        self._service = build("searchconsole", "v1", credentials=credentials)
        self._property = property_url

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def get_page_data(self, start: date, end: date) -> dict[str, dict[str, Any]]:
        """Return per-page aggregated metrics for a date range.

        Returns:
            Mapping of ``url -> {clicks, impressions, ctr, position}``.
        """
        rows = self._query(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            dimensions=["page"],
        )
        return {
            row["keys"][0]: {
                "clicks": row["clicks"],
                "impressions": row["impressions"],
                "ctr": row["ctr"],
                "position": row["position"],
            }
            for row in rows
        }

    def get_keyword_data(
        self, start: date, end: date
    ) -> dict[str, list[dict[str, Any]]]:
        """Return per-(page, query) metrics for a date range.

        Returns:
            Mapping of ``url -> [{query, clicks, impressions, ctr, position}, ...]``.
        """
        rows = self._query(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            dimensions=["page", "query"],
        )
        result: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            url, query = row["keys"][0], row["keys"][1]
            result.setdefault(url, []).append(
                {
                    "query": query,
                    "clicks": row["clicks"],
                    "impressions": row["impressions"],
                    "ctr": row["ctr"],
                    "position": row["position"],
                }
            )
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query(
        self,
        start_date: str,
        end_date: str,
        dimensions: list[str],
    ) -> list[dict[str, Any]]:
        """Execute a paginated searchanalytics.query request."""
        all_rows: list[dict[str, Any]] = []
        start_row = 0

        while True:
            body = {
                "startDate": start_date,
                "endDate": end_date,
                "dimensions": dimensions,
                "rowLimit": _MAX_ROWS,
                "startRow": start_row,
            }
            try:
                response = (
                    self._service.searchanalytics()
                    .query(siteUrl=self._property, body=body)
                    .execute()
                )
            except HttpError as exc:
                if exc.resp.status == 429:
                    console.print(
                        f"[yellow]Rate limited — waiting {_RETRY_DELAY}s…[/yellow]"
                    )
                    time.sleep(_RETRY_DELAY)
                    continue
                raise

            rows: list[dict[str, Any]] = response.get("rows", [])
            all_rows.extend(rows)

            # GSC returns fewer rows than requested when we've hit the end
            if len(rows) < _MAX_ROWS:
                break
            start_row += _MAX_ROWS

        return all_rows
