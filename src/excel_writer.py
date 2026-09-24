"""Builds/overwrites the tracker spreadsheet. No dated snapshots — this
always writes to the same path, overwriting whatever was there before.

The workbook has five sheets:
- "All titles" — everything, as a flat table.
- "Free", "Subscription", "Rent-Buy", "Unavailable" — a strict partition of
  the same data: every title lands on exactly one of these four, based on
  its best available option (free beats subscription beats rent/buy beats
  nothing found). "Unavailable" covers both "found on TMDb but no option
  anywhere" and "not found on TMDb at all" — the Availability column still
  distinguishes those two within that sheet.

Every sheet uses the same columns and has an Excel AutoFilter turned on, so
you can sort or filter by rating, genre, or anything else directly in
Excel. Rows are still color-coded by availability tier via background
fill, but that's a per-row cell property rather than a merged banner row —
merged cells break Excel's native sort, so this keeps the color cue without
giving up sortability.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import List, Tuple

from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from .models import WatchlistTitle
from .poster_fetcher import POSTER_SIZE

HEADERS = [
    "Poster",
    "Title",
    "Year",
    "IMDb Rating",
    "Genres",
    "Runtime (min)",
    "Director(s)",
    "Availability",
    "Subscription Services",
    "Rent/Buy",
    "Free (Ad-Supported)",
    "Free (YouTube - Unverified)",
    "Last Checked",
]

COLUMN_WIDTHS = [7, 32, 8, 12, 30, 13, 24, 26, 28, 28, 28, 45, 20]

TITLE_COLUMN = 2  # 1-indexed; keep in sync with HEADERS above
POSTER_ROW_HEIGHT = 54

NOT_FOUND = "Not found"
NONE_LABEL = "—"  # em dash

THIN_BORDER = Border(*(Side(style="thin", color="D9D9D9") for _ in range(4)))

# tier -> (row fill hex, label shown in the Availability column), ordered
# most-actionable (a real free option) first, least (no TMDb match) last.
TIER_STYLE = {
    1: ("C6EFCE", "Free (ad-supported)"),
    2: ("DAEEF3", "Free (YouTube, unverified)"),
    3: ("FFEB9C", "Subscription"),
    4: ("DCE6F1", "Rent/Buy"),
    5: ("F2F2F2", "No availability found"),
    6: ("FFC7CE", "Not found on TMDb"),
}


def _lighten(hex_color: str, factor: float = 0.5) -> str:
    """Blends a hex color toward white by `factor` (0 = unchanged, 1 = white)."""
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (0, 2, 4))
    r, g, b = (round(c + (255 - c) * factor) for c in (r, g, b))
    return f"{r:02X}{g:02X}{b:02X}"


def _tier(title: WatchlistTitle) -> int:
    if not title.tmdb_found:
        return 6
    if title.free_ad_supported:
        return 1
    if title.youtube_matches:
        return 2
    if title.subscription:
        return 3
    if title.rent_buy:
        return 4
    return 5


def _join(items: List[str]) -> str:
    return ", ".join(items) if items else NONE_LABEL


def _youtube_cell(title: WatchlistTitle) -> str:
    if not title.youtube_matches:
        return NONE_LABEL
    parts = [
        f"unverified - check manually: {m.video_title} ({m.channel_name}) {m.url}"
        for m in title.youtube_matches
    ]
    return "\n".join(parts)


def _row_values(title: WatchlistTitle, tier: int) -> list:
    if not title.tmdb_found:
        subscription = rent_buy = free_ad = NOT_FOUND
    else:
        subscription = _join(title.subscription)
        rent_buy = _join(title.rent_buy)
        free_ad = _join(title.free_ad_supported)

    return [
        "",  # Poster — image is overlaid on this cell separately, not a text value
        title.title,
        title.year or "",
        title.imdb_rating if title.imdb_rating is not None else NONE_LABEL,
        _join(title.genres),
        title.runtime_minutes if title.runtime_minutes is not None else NONE_LABEL,
        _join(title.directors),
        TIER_STYLE[tier][1],
        subscription,
        rent_buy,
        free_ad,
        _youtube_cell(title),
        title.last_checked or "",
    ]


def _write_sheet(ws: Worksheet, titles: List[WatchlistTitle]) -> None:
    n_cols = len(HEADERS)

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        cell.border = THIN_BORDER
    ws.freeze_panes = "A2"

    # Sensible default order when the sheet is first opened — grouped by
    # tier, alphabetical within each. The AutoFilter (below) lets the user
    # re-sort by rating, genre, or anything else afterward; per-row fill
    # color always reflects that row's real tier regardless of how it's
    # currently sorted, since it's a cell property, not a banner row.
    grouped: List[Tuple[int, WatchlistTitle]] = sorted(
        ((_tier(t), t) for t in titles), key=lambda pair: (pair[0], pair[1].title.lower())
    )

    current_tier = None
    row_in_tier = 0

    for tier, title in grouped:
        if tier != current_tier:
            current_tier = tier
            row_in_tier = 0

        row_fill = TIER_STYLE[tier][0]
        shade = row_fill if row_in_tier % 2 == 0 else _lighten(row_fill, 0.5)
        row_in_tier += 1

        ws.append(_row_values(title, tier))
        row_idx = ws.max_row
        ws.row_dimensions[row_idx].height = POSTER_ROW_HEIGHT

        for col in range(1, n_cols + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.fill = PatternFill("solid", fgColor=shade)
            cell.border = THIN_BORDER

        title_cell = ws.cell(row=row_idx, column=TITLE_COLUMN)
        title_cell.hyperlink = f"https://www.imdb.com/title/{title.imdb_id}/"
        title_cell.font = Font(color="0563C1", underline="single")

        if title.poster_image:
            # A fresh Image instance per sheet — the same title can appear
            # on multiple sheets (e.g. Subscription and Rent-Buy), and an
            # openpyxl Image can't be shared across worksheets.
            img = XLImage(BytesIO(title.poster_image))
            img.width, img.height = POSTER_SIZE
            ws.add_image(img, f"A{row_idx}")

    for idx, width in enumerate(COLUMN_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    ws.auto_filter.ref = f"A1:{get_column_letter(n_cols)}{ws.max_row}"


def write_excel(titles: List[WatchlistTitle], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    all_ws = wb.active
    all_ws.title = "All titles"
    _write_sheet(all_ws, titles)

    # Each title's tier (see _tier) already resolves to exactly one
    # priority level — free beats subscription beats rent/buy beats
    # nothing found — so grouping by tier gives a strict partition: every
    # title lands on exactly one of these four sheets, never more than one.
    free_titles = [t for t in titles if _tier(t) in (1, 2)]
    subscription_titles = [t for t in titles if _tier(t) == 3]
    rent_buy_titles = [t for t in titles if _tier(t) == 4]
    unavailable_titles = [t for t in titles if _tier(t) in (5, 6)]

    _write_sheet(wb.create_sheet("Free"), free_titles)
    _write_sheet(wb.create_sheet("Subscription"), subscription_titles)
    _write_sheet(wb.create_sheet("Rent-Buy"), rent_buy_titles)
    _write_sheet(wb.create_sheet("Unavailable"), unavailable_titles)

    wb.save(output_path)
