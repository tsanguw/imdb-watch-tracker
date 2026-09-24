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
    poster_url: Optional[str] = None  # from TMDb, set once a match is found
    poster_image: Optional[bytes] = None  # downloaded + resized PNG bytes, ready to embed

    tmdb_found: bool = False
    tmdb_id: Optional[int] = None
    tmdb_media_type: Optional[str] = None  # "movie" or "tv"

    # From IMDb's own CSV export — no extra API calls needed for these.
    imdb_rating: Optional[float] = None
    genres: List[str] = field(default_factory=list)
    runtime_minutes: Optional[int] = None
    directors: List[str] = field(default_factory=list)
    num_votes: Optional[int] = None

    subscription: List[str] = field(default_factory=list)
    rent_buy: List[str] = field(default_factory=list)
    free_ad_supported: List[str] = field(default_factory=list)

    youtube_matches: List[YouTubeMatch] = field(default_factory=list)

    last_checked: Optional[str] = None
