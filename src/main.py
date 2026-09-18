"""Entry point: read watchlist CSV -> enrich -> write Excel.

Run via `python -m src.main` (locally, with a .env file — see
.env.example) or from the GitHub Actions workflow (.github/workflows/update.yml),
which sets the same environment variables from repo secrets/variables.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from . import config
from .excel_writer import write_excel
from .poster_fetcher import fetch_poster_image
from .tmdb_client import TMDbClient, TMDbError
from .watchlist_csv import WatchlistCSVError, load_watchlist_csv
from .youtube_client import YouTubeClient, load_allowed_channels


def run(cfg: config.Config) -> None:
    session = config.make_session()

    print(f"Reading watchlist from {cfg.watchlist_csv_path}...")
    titles = load_watchlist_csv(cfg.watchlist_csv_path)
    print(f"Found {len(titles)} titles.")

    tmdb = TMDbClient(session, cfg.tmdb_api_key, region=cfg.region)

    allowed_channels = load_allowed_channels(cfg.youtube_channels_path)
    if not allowed_channels:
        print(
            f"[main] Warning: no YouTube channels configured in "
            f"{cfg.youtube_channels_path} — the 'Free (YouTube)' column "
            "will be empty for every title until channel_id values are "
            "filled in (see README)."
        )
    youtube = YouTubeClient(session, cfg.youtube_api_key, allowed_channels)

    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    for i, title in enumerate(titles, start=1):
        print(f"[{i}/{len(titles)}] {title.title} ({title.year})")
        title.last_checked = checked_at

        try:
            match = tmdb.find_by_imdb_id(title.imdb_id, title.title_type)
        except TMDbError as exc:
            raise TMDbError(
                f"TMDb lookup failed for {title.imdb_id} ({title.title}): {exc}"
            ) from exc

        if match is None:
            title.tmdb_found = False
        else:
            title.tmdb_found = True
            title.tmdb_id, title.tmdb_media_type = match.tmdb_id, match.media_type
            title.poster_url = match.poster_url
            if title.poster_url:
                title.poster_image = fetch_poster_image(title.poster_url, session)

            providers = tmdb.get_watch_providers(title.tmdb_id, title.tmdb_media_type)
            title.subscription = providers.subscription
            title.rent_buy = providers.rent_buy
            title.free_ad_supported = providers.free_ad_supported

        # Save YouTube API quota: skip the (least reliable) YouTube search
        # for anything that already has a confirmed free ad-supported
        # option from TMDb, unless the caller explicitly asked to
        # force-recheck (workflow_dispatch input / --force-youtube-recheck).
        already_free = bool(title.free_ad_supported)
        if already_free and not cfg.force_youtube_recheck:
            continue

        yt_match = youtube.search_free_movie(title.title, title.year)
        if yt_match:
            title.youtube_matches = [yt_match]

    write_excel(titles, cfg.output_path)
    print(f"Wrote {len(titles)} titles to {cfg.output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh the IMDb watchlist tracker spreadsheet."
    )
    parser.add_argument(
        "--force-youtube-recheck",
        action="store_true",
        help="Check YouTube even for titles that already have a free ad-supported match.",
    )
    args = parser.parse_args()

    try:
        cfg = config.load_config()
    except config.ConfigError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.force_youtube_recheck:
        cfg.force_youtube_recheck = True

    try:
        run(cfg)
    except (WatchlistCSVError, TMDbError) as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
