"""Environment/config loading and a shared HTTP session with retries."""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


@dataclass
class Config:
    imdb_user_id: str
    tmdb_api_key: str
    youtube_api_key: str
    region: str = "US"
    output_path: str = "data/watchlist.xlsx"
    force_youtube_recheck: bool = False
    youtube_channels_path: str = "config/youtube_channels.json"


def load_config() -> Config:
    missing = []
    imdb_user_id = os.environ.get("IMDB_USER_ID")
    tmdb_api_key = os.environ.get("TMDB_API_KEY")
    youtube_api_key = os.environ.get("YOUTUBE_API_KEY")

    if not imdb_user_id:
        missing.append("IMDB_USER_ID")
    if not tmdb_api_key:
        missing.append("TMDB_API_KEY")
    if not youtube_api_key:
        missing.append("YOUTUBE_API_KEY")

    if missing:
        raise ConfigError(
            "Missing required configuration: "
            + ", ".join(missing)
            + ". Set these as environment variables, or in a local .env "
            "file based on .env.example."
        )

    force_youtube = os.environ.get("FORCE_YOUTUBE_RECHECK", "false").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    return Config(
        imdb_user_id=imdb_user_id,
        tmdb_api_key=tmdb_api_key,
        youtube_api_key=youtube_api_key,
        region=os.environ.get("TMDB_REGION", "US"),
        output_path=os.environ.get("OUTPUT_PATH", "data/watchlist.xlsx"),
        force_youtube_recheck=force_youtube,
        youtube_channels_path=os.environ.get(
            "YOUTUBE_CHANNELS_PATH", "config/youtube_channels.json"
        ),
    )


def make_session(total_retries: int = 2, backoff_factor: float = 2.0) -> requests.Session:
    """A requests.Session with a small number of retries on transient
    errors (connection failures, 429/5xx). This is per-request retry only —
    it will NOT retry a clean 200 response that just doesn't contain the
    data we expect. That's a data-shape problem, not a transient one, and
    should fail loudly instead of being masked by a retry loop. See
    imdb_scraper.fetch_watchlist for the separate whole-fetch retry that
    covers bot-detection-style failures.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    retry = Retry(
        total=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
