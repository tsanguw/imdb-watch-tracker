"""Shared data structures used across the pipeline."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class YouTubeMatch:
    video_title: str
    url: str
    channel_name: str


@dataclass
class WatchlistTitle:
    """A single title pulled from the IMDb watchlist, later enriched with
    TMDb watch-provider data and a heuristic YouTube match."""

    imdb_id: str
    title: str
    year: Optional[int]
    title_type: str  # "movie", "tvSeries", "tvMiniSeries", ...
    poster_url: Optional[str] = None

    tmdb_found: bool = False
    tmdb_id: Optional[int] = None
    tmdb_media_type: Optional[str] = None  # "movie" or "tv"

    subscription: List[str] = field(default_factory=list)
    rent_buy: List[str] = field(default_factory=list)
    free_ad_supported: List[str] = field(default_factory=list)

    youtube_matches: List[YouTubeMatch] = field(default_factory=list)

    last_checked: Optional[str] = None
