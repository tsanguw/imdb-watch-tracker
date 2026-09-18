"""Reads your IMDb watchlist from a manually-exported CSV file.

This project originally tried to fetch the watchlist by driving a headless
browser against IMDb's live watchlist page. That page turned out to be
protected by an AWS WAF "Human Verification" challenge (a CAPTCHA-style
control, not just IP-based rate limiting) that blocks automated browser
access outright. Defeating that kind of check isn't something this project
will do, even for personal use against your own public data — so there is
no way to fetch this data programmatically at all.

Instead: export your watchlist yourself, as a normal signed-in action in
your own real browser (IMDb watchlist page -> "..." menu -> Export), and
save the resulting CSV to the path this module reads (see config.py /
README). Everything downstream — TMDb lookups, YouTube search, the Excel
output, the weekly schedule — still runs automatically; only the watchlist
snapshot itself needs a manual refresh when you add or remove titles.

IMDb's exported CSV column set has changed over the years and could change
again, so this fails loudly (raises WatchlistCSVError) and reports the
columns it actually found whenever the file doesn't have the shape this
project expects, rather than silently skipping or misreading rows.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Optional

from .models import WatchlistTitle

REQUIRED_COLUMNS = ("Const", "Title", "Title Type")


class WatchlistCSVError(RuntimeError):
    """Raised when the watchlist CSV is missing, empty, or an unexpected shape."""


def _parse_year(row: dict) -> Optional[int]:
    year_str = (row.get("Year") or "").strip()
    if year_str.isdigit():
        return int(year_str)

    # Some export variants have used "Release Date" (e.g. "1994-10-14")
    # instead of a plain "Year" column.
    release_date = (row.get("Release Date") or "").strip()
    if len(release_date) >= 4 and release_date[:4].isdigit():
        return int(release_date[:4])

    return None


def load_watchlist_csv(path: str) -> List[WatchlistTitle]:
    file_path = Path(path)
    if not file_path.exists():
        raise WatchlistCSVError(
            f"Watchlist CSV not found at {path}. Export it from your IMDb "
            'watchlist (the "..." menu -> Export) and save it there — see '
            "the README for the exact steps."
        )

    # utf-8-sig quietly strips a BOM if Excel/IMDb's export includes one.
    with file_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []

        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise WatchlistCSVError(
                f"Watchlist CSV at {path} is missing expected column(s) "
                f"{missing}. Columns found: {fieldnames}. IMDb's export "
                "format may have changed since this was written — update "
                "REQUIRED_COLUMNS in src/watchlist_csv.py to match."
            )

        titles: List[WatchlistTitle] = []
        seen_ids = set()
        for i, row in enumerate(reader, start=2):  # row 1 is the header
            imdb_id = (row.get("Const") or "").strip()
            title_text = (row.get("Title") or "").strip()
            title_type = (row.get("Title Type") or "").strip() or "unknown"

            if not imdb_id or not imdb_id.startswith("tt") or not title_text:
                raise WatchlistCSVError(
                    f"Row {i} in {path} is malformed "
                    f"(Const={imdb_id!r}, Title={title_text!r})."
                )

            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)

            titles.append(
                WatchlistTitle(
                    imdb_id=imdb_id,
                    title=title_text,
                    year=_parse_year(row),
                    title_type=title_type,
                )
            )

    if not titles:
        raise WatchlistCSVError(
            f"Watchlist CSV at {path} parsed successfully but contained no "
            "titles. Refusing to overwrite the spreadsheet with an empty "
            "result — if your watchlist really is empty, remove the output "
            "file manually instead of relying on this to clear it."
        )

    return titles
