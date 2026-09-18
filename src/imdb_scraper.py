"""Scrapes a public IMDb watchlist by reading the __NEXT_DATA__ JSON blob
that IMDb's Next.js frontend embeds in the server-rendered HTML.

This is deliberately NOT a DOM/CSS scraper: __NEXT_DATA__ is a typed data
structure IMDb's own frontend hydrates from (confirmed by inspecting a live
IMDb list page), so it's less brittle than class-name scraping. But the
exact key paths are still an undocumented internal contract that can change
without notice, and pagination behavior for watchlists over ~100 titles
could not be verified directly (see fetch_watchlist docstring). If IMDb
changes the shape of this data, every function below is written to raise
ScraperError loudly rather than return an empty or partial watchlist.
"""
from __future__ import annotations

import json
import re
import sys
import time
from typing import List, Optional, Tuple

import requests

from .models import WatchlistTitle

NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
    re.DOTALL,
)

# Sanity limit on pagination — a real bug should trip the total-count check
# in _fetch_watchlist_once long before this is ever reached.
MAX_PAGES = 20


class ScraperError(RuntimeError):
    """Raised whenever the IMDb page doesn't have the shape we expect."""


def _watchlist_url(user_id: str, page: int = 1) -> str:
    base = f"https://www.imdb.com/user/{user_id}/watchlist/"
    return base if page == 1 else f"{base}?page={page}"


def _extract_next_data(html: str, url: str) -> dict:
    match = NEXT_DATA_RE.search(html)
    if not match:
        raise ScraperError(
            f"Could not find a __NEXT_DATA__ script tag at {url}. IMDb may "
            "have changed its page structure, or this page requires "
            "authentication (make sure the watchlist's privacy is set to "
            "Public in IMDb's account settings)."
        )
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ScraperError(f"__NEXT_DATA__ at {url} was not valid JSON: {exc}") from exc


def _dig(data: dict, *path: str):
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            raise ScraperError(
                "Expected key path '"
                + ".".join(path)
                + f"' not found (stopped at '{key}'). IMDb's internal page "
                "data structure has likely changed and this scraper needs "
                "updating (see src/imdb_scraper.py)."
            )
        node = node[key]
    return node


def _parse_page(data: dict) -> Tuple[List[WatchlistTitle], dict, int]:
    list_data = _dig(data, "props", "pageProps", "mainColumnData", "list")
    search = _dig(list_data, "titleListItemSearch")

    edges = search.get("edges")
    if edges is None:
        raise ScraperError("titleListItemSearch.edges missing from watchlist response.")

    total = search.get("total")
    if total is None:
        raise ScraperError("titleListItemSearch.total missing from watchlist response.")

    page_info = search.get("pageInfo") or {}

    titles: List[WatchlistTitle] = []
    for edge in edges:
        item = edge.get("listItem")
        if not item:
            raise ScraperError("A watchlist edge had no listItem — unexpected shape.")

        imdb_id = item.get("id")
        title_text = (item.get("titleText") or {}).get("text")
        if not imdb_id or not isinstance(imdb_id, str) or not imdb_id.startswith("tt") or not title_text:
            raise ScraperError(
                f"Malformed watchlist item (id={imdb_id!r}, title={title_text!r})."
            )

        year: Optional[int] = None
        release_year = item.get("releaseYear")
        if release_year:
            year = release_year.get("year")

        title_type = (item.get("titleType") or {}).get("id", "unknown")

        poster_url = None
        primary_image = item.get("primaryImage")
        if primary_image:
            poster_url = primary_image.get("url")

        titles.append(
            WatchlistTitle(
                imdb_id=imdb_id,
                title=title_text,
                year=year,
                title_type=title_type,
                poster_url=poster_url,
            )
        )

    return titles, page_info, total


def _fetch_watchlist_once(user_id: str, session: requests.Session) -> List[WatchlistTitle]:
    all_titles: List[WatchlistTitle] = []
    seen_ids: set = set()
    expected_total: Optional[int] = None
    page = 1

    while True:
        url = _watchlist_url(user_id, page)
        response = session.get(url, timeout=30)
        if response.status_code != 200:
            raise ScraperError(f"GET {url} returned HTTP {response.status_code}.")

        data = _extract_next_data(response.text, url)
        titles, page_info, total = _parse_page(data)

        if expected_total is None:
            expected_total = total
        elif total != expected_total:
            raise ScraperError(
                f"Watchlist total changed mid-scrape ({expected_total} -> {total}); "
                "the list may have been edited while this ran. Aborting rather "
                "than guessing which count is right."
            )

        new_count = 0
        for t in titles:
            if t.imdb_id not in seen_ids:
                seen_ids.add(t.imdb_id)
                all_titles.append(t)
                new_count += 1

        if len(all_titles) >= expected_total:
            break

        if new_count == 0:
            # Asked for another page and got nothing new back. Either we've
            # actually reached the end despite `total` disagreeing, or (more
            # likely) IMDb's watchlist pagination doesn't follow the
            # "?page=N" scheme this scraper assumes for lists over ~100
            # items (that assumption was never verified against a real
            # >100-item watchlist — see project README). Fail loudly rather
            # than silently returning a partial list either way.
            raise ScraperError(
                f"Collected {len(all_titles)} of {expected_total} titles but "
                "the next page returned no new items. IMDb's watchlist "
                "pagination may not follow the '?page=N' scheme this "
                "scraper assumes — this needs verifying against a watchlist "
                "with more than 100 titles, and imdb_scraper.py updated."
            )

        if not page_info.get("hasNextPage", False):
            raise ScraperError(
                f"Collected {len(all_titles)} of {expected_total} titles but "
                "pageInfo.hasNextPage is False. Aborting instead of "
                "returning a partial watchlist."
            )

        page += 1
        if page > MAX_PAGES:
            raise ScraperError(
                f"Exceeded {MAX_PAGES} pages while paginating the watchlist "
                f"({len(all_titles)} of {expected_total} collected)."
            )

    return all_titles


def fetch_watchlist(
    user_id: str,
    session: requests.Session,
    max_attempts: int = 2,
    retry_delay_seconds: float = 8.0,
) -> List[WatchlistTitle]:
    """Fetch the full public watchlist for `user_id`, following pagination
    and validating the collected count against IMDb's own reported total.

    Retries the *whole* fetch up to `max_attempts` times on failure. This is
    separate from the per-request retries already configured on `session`
    (config.make_session), and specifically covers bot-detection-style
    failures that don't look like a clean 5xx — e.g. a 200 response with an
    interstitial/CAPTCHA page that has no __NEXT_DATA__ at all, which a
    plain HTTP-status retry wouldn't catch.
    """
    last_error: Optional[Exception] = None
    for attempt in range(1, max_attempts + 1):
        try:
            return _fetch_watchlist_once(user_id, session)
        except (ScraperError, requests.RequestException) as exc:
            last_error = exc
            if attempt < max_attempts:
                print(
                    f"[imdb_scraper] Attempt {attempt}/{max_attempts} failed "
                    f"({exc}); retrying in {retry_delay_seconds:.0f}s...",
                    file=sys.stderr,
                )
                time.sleep(retry_delay_seconds)

    raise ScraperError(
        f"Failed to scrape watchlist after {max_attempts} attempts: {last_error}"
    ) from last_error
