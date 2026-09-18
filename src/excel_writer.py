"""Builds/overwrites the tracker spreadsheet. No dated snapshots — this
always writes to the same path, overwriting whatever was there before.

Rows are grouped into availability tiers (free options first, "Not found"
last) with a labeled, colored section divider between each group, and
color-coded so the sheet is scannable at a glance without reading every
cell.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import WatchlistTitle

HEADERS = [
    "Title",
    "Year",
    "Subscription Services",
    "Rent/Buy",
    "Free (Ad-Supported)",
    "Free (YouTube - Unverified)",
    "Last Checked",
]

COLUMN_WIDTHS = [32, 8, 28, 28, 28, 45, 20]

NOT_FOUND = "Not found"
NONE_LABEL = "—"  # em dash

THIN_BORDER = Border(*(Side(style="thin", color="D9D9D9") for _ in range(4)))

# (row_fill, divider_fill, divider_font_color, label) per tier, in the order
# rows should appear — most actionable (a real free option) first, "Not
# found" last.
TIER_STYLE = {
    1: ("C6EFCE", "375623", "FFFFFF", "✓ FREE TO WATCH (AD-SUPPORTED)"),
    2: ("DAEEF3", "1F4E5F", "FFFFFF", "POSSIBLY FREE ON YOUTUBE (UNVERIFIED)"),
    3: ("FFEB9C", "7F6000", "FFFFFF", "SUBSCRIPTION ONLY"),
    4: ("DCE6F1", "1F4E79", "FFFFFF", "RENT / BUY ONLY"),
    5: ("F2F2F2", "595959", "FFFFFF", "NO AVAILABILITY FOUND"),
    6: ("FFC7CE", "9C0006", "FFFFFF", "NOT FOUND ON TMDB"),
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


def _row_values(title: WatchlistTitle) -> list:
    if not title.tmdb_found:
        subscription = rent_buy = free_ad = NOT_FOUND
    else:
        subscription = _join(title.subscription)
        rent_buy = _join(title.rent_buy)
        free_ad = _join(title.free_ad_supported)

    return [
        title.title,
        title.year or "",
        subscription,
        rent_buy,
        free_ad,
        _youtube_cell(title),
        title.last_checked or "",
    ]


def write_excel(titles: List[WatchlistTitle], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Watchlist"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(vertical="top", wrap_text=True)
        cell.border = THIN_BORDER
    ws.freeze_panes = "A2"

    grouped: List[Tuple[int, WatchlistTitle]] = sorted(
        ((_tier(t), t) for t in titles), key=lambda pair: (pair[0], pair[1].title.lower())
    )

    n_cols = len(HEADERS)
    current_tier = None
    row_in_tier = 0

    for tier, title in grouped:
        if tier != current_tier:
            current_tier = tier
            row_in_tier = 0
            row_fill, divider_fill, divider_font_color, label = TIER_STYLE[tier]

            ws.append([label] + [""] * (n_cols - 1))
            divider_row = ws.max_row
            ws.merge_cells(start_row=divider_row, start_column=1, end_row=divider_row, end_column=n_cols)
            for col in range(1, n_cols + 1):
                cell = ws.cell(row=divider_row, column=col)
                cell.fill = PatternFill("solid", fgColor=divider_fill)
                cell.font = Font(bold=True, color=divider_font_color)
                cell.border = THIN_BORDER
            ws.cell(row=divider_row, column=1).alignment = Alignment(vertical="center")

        row_fill = TIER_STYLE[tier][0]
        shade = row_fill if row_in_tier % 2 == 0 else _lighten(row_fill, 0.5)
        row_in_tier += 1

        ws.append(_row_values(title))
        row_idx = ws.max_row

        for col in range(1, n_cols + 1):
            cell = ws.cell(row=row_idx, column=col)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.fill = PatternFill("solid", fgColor=shade)
            cell.border = THIN_BORDER

        title_cell = ws.cell(row=row_idx, column=1)
        title_cell.hyperlink = f"https://www.imdb.com/title/{title.imdb_id}/"
        title_cell.font = Font(color="0563C1", underline="single")

    for idx, width in enumerate(COLUMN_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    wb.save(output_path)
