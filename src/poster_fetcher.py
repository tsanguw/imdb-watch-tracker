"""Downloads and resizes TMDb poster thumbnails for embedding in the Excel
output.

This is purely cosmetic, unlike the streaming-availability data — a poster
that fails to download shouldn't take down the whole run, so failures here
are swallowed and just leave that title's Poster cell blank rather than
raising. Network/image errors are logged so they're visible, not silent.
"""
from __future__ import annotations

import io
from typing import Optional, Tuple

import requests
from PIL import Image as PILImage
from PIL import UnidentifiedImageError

# (width, height) in pixels, matched to POSTER_ROW_HEIGHT / POSTER_COLUMN_WIDTH
# in excel_writer.py — change all three together if you want bigger/smaller
# thumbnails.
POSTER_SIZE: Tuple[int, int] = (45, 68)


def fetch_poster_image(url: str, session: requests.Session) -> Optional[bytes]:
    """Downloads the poster at `url`, resizes it to fit within POSTER_SIZE
    (preserving aspect ratio), and returns it as PNG bytes — or None if
    anything goes wrong."""
    try:
        response = session.get(url, timeout=15)
        if response.status_code != 200:
            print(f"[poster_fetcher] HTTP {response.status_code} fetching {url}")
            return None

        image = PILImage.open(io.BytesIO(response.content))
        image = image.convert("RGB")
        image.thumbnail(POSTER_SIZE)

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()
    except (requests.RequestException, UnidentifiedImageError, OSError) as exc:
        print(f"[poster_fetcher] Could not fetch/process poster from {url}: {exc}")
        return None
