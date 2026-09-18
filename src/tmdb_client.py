"""TMDb client: IMDb ID -> TMDb ID -> watch providers.

Matching is done strictly by IMDb ID via TMDb's /find endpoint, never by
title/name, to avoid false positives on similarly-named titles.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests

TMDB_BASE = "https://api.themoviedb.org/3"


class TMDbError(RuntimeError):
    """Raised when TMDb can't be reached or returns an unexpected shape."""


@dataclass
class ProviderResult:
    subscription: List[str] = field(default_factory=list)
    rent_buy: List[str] = field(default_factory=list)
    free_ad_supported: List[str] = field(default_factory=list)


class TMDbClient:
    def __init__(self, session: requests.Session, api_key: str, region: str = "US"):
        self.session = session
        self.api_key = api_key
        self.region = region

    def _get(self, path: str, **params) -> dict:
        params["api_key"] = self.api_key
        try:
            response = self.session.get(f"{TMDB_BASE}{path}", params=params, timeout=30)
        except requests.RequestException as exc:
            raise TMDbError(f"Request to {path} failed: {exc}") from exc

        if response.status_code == 404:
            return {}
        if response.status_code != 200:
            raise TMDbError(
                f"TMDb GET {path} returned HTTP {response.status_code}: {response.text[:300]}"
            )
        return response.json()

    def find_by_imdb_id(self, imdb_id: str, title_type: str) -> Optional[Tuple[int, str]]:
        """Returns (tmdb_id, media_type) or None if there's no match at all.

        `title_type` is IMDb's titleType.id (e.g. "movie", "tvSeries") and
        is used only to disambiguate when TMDb returns both a movie and a
        tv result for the same IMDb ID — it never drives the ID match
        itself.
        """
        data = self._get(f"/find/{imdb_id}", external_source="imdb_id")
        movie_results = data.get("movie_results") or []
        tv_results = data.get("tv_results") or []

        wants_tv = title_type in ("tvSeries", "tvMiniSeries", "tvSpecial")

        if wants_tv and tv_results:
            return tv_results[0]["id"], "tv"
        if not wants_tv and movie_results:
            return movie_results[0]["id"], "movie"

        # Fall back to whichever list is non-empty, in case IMDb's
        # titleType and TMDb's classification disagree for an edge case.
        if movie_results:
            return movie_results[0]["id"], "movie"
        if tv_results:
            return tv_results[0]["id"], "tv"

        return None

    def get_watch_providers(self, tmdb_id: int, media_type: str) -> ProviderResult:
        kind = "movie" if media_type == "movie" else "tv"
        data = self._get(f"/{kind}/{tmdb_id}/watch/providers")
        region_data = (data.get("results") or {}).get(self.region, {})

        def names(key: str) -> List[str]:
            return [p["provider_name"] for p in region_data.get(key, [])]

        subscription = sorted(set(names("flatrate")))
        rent_buy = sorted(set(names("rent")) | set(names("buy")))
        # TMDb splits ad-supported free content across "free" and "ads" —
        # both surface things like Tubi and Pluto TV depending on the
        # title, so both are combined into one column.
        free_ad_supported = sorted(set(names("free")) | set(names("ads")))

        return ProviderResult(
            subscription=subscription,
            rent_buy=rent_buy,
            free_ad_supported=free_ad_supported,
        )
