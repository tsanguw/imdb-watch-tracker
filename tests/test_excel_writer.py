import io

from openpyxl import load_workbook
from PIL import Image as PILImage

from src.excel_writer import HEADERS, TIER_STYLE, write_excel
from src.models import WatchlistTitle, YouTubeMatch

# Column indices (0-indexed, matching HEADERS) so tests read clearly and
# stay correct if columns are reordered.
POSTER_COL = 0
TITLE_COL = 1
SUBSCRIPTION_COL = 3
RENT_BUY_COL = 4
FREE_AD_COL = 5


def _tiny_png_bytes() -> bytes:
    image = PILImage.new("RGB", (10, 15), color=(10, 20, 30))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _make_titles():
    return [
        WatchlistTitle(
            imdb_id="tt1",
            title="Has Free Ad-Supported",
            year=2020,
            title_type="movie",
            tmdb_found=True,
            subscription=["Netflix"],
            rent_buy=["Amazon Video"],
            free_ad_supported=["Tubi"],
            poster_image=_tiny_png_bytes(),
        ),
        WatchlistTitle(
            imdb_id="tt2",
            title="Only On YouTube Unverified",
            year=2019,
            title_type="movie",
            tmdb_found=True,
            youtube_matches=[YouTubeMatch("Full Movie", "https://youtube.com/x", "Some Studio")],
        ),
        WatchlistTitle(
            imdb_id="tt3",
            title="Subscription Only Title",
            year=2018,
            title_type="movie",
            tmdb_found=True,
            subscription=["Netflix"],
        ),
        WatchlistTitle(
            imdb_id="tt4",
            title="Rent Buy Only Title",
            year=2017,
            title_type="movie",
            tmdb_found=True,
            rent_buy=["Apple TV Store"],
        ),
        WatchlistTitle(
            imdb_id="tt5",
            title="Found But No Availability",
            year=2016,
            title_type="movie",
            tmdb_found=True,
        ),
        WatchlistTitle(
            imdb_id="tt6",
            title="Totally Unfound Title",
            year=2015,
            title_type="movie",
            tmdb_found=False,
        ),
    ]


def _row_by_title(ws, title_text):
    for row in ws.iter_rows(min_row=2):
        if row[TITLE_COL].value == title_text:
            return row
    return None


def _divider_rows(ws):
    """Returns [(row_index, label)] for every merged section-divider row,
    in the order they appear top to bottom."""
    dividers = []
    for row in ws.iter_rows(min_row=2):
        first_cell = row[0].value
        if first_cell in {label for _, _, _, label in TIER_STYLE.values()}:
            dividers.append((row[0].row, first_cell))
    return dividers


def test_write_excel_header(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))
    wb = load_workbook(output_path)
    ws = wb.active
    assert [c.value for c in ws[1]] == HEADERS


def test_write_excel_groups_and_labels_tiers(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active

    dividers = _divider_rows(ws)
    labels_in_order = [label for _, label in dividers]
    assert labels_in_order == [
        "✓ FREE TO WATCH (AD-SUPPORTED)",
        "POSSIBLY FREE ON YOUTUBE (UNVERIFIED)",
        "SUBSCRIPTION ONLY",
        "RENT / BUY ONLY",
        "NO AVAILABILITY FOUND",
        "NOT FOUND ON TMDB",
    ]

    free_divider_row = dividers[0][0]
    not_found_divider_row = dividers[5][0]

    free_row = _row_by_title(ws, "Has Free Ad-Supported")[0].row
    not_found_row = _row_by_title(ws, "Totally Unfound Title")[0].row

    assert free_divider_row < free_row < not_found_divider_row < not_found_row


def test_write_excel_not_found_shows_not_found_label(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active

    row = _row_by_title(ws, "Totally Unfound Title")
    assert row[SUBSCRIPTION_COL].value == "Not found"
    assert row[RENT_BUY_COL].value == "Not found"
    assert row[FREE_AD_COL].value == "Not found"


def test_write_excel_row_values_and_hyperlink(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active

    row = _row_by_title(ws, "Has Free Ad-Supported")
    assert row[SUBSCRIPTION_COL].value == "Netflix"
    assert row[RENT_BUY_COL].value == "Amazon Video"
    assert row[FREE_AD_COL].value == "Tubi"
    assert row[TITLE_COL].hyperlink.target == "https://www.imdb.com/title/tt1/"


def test_write_excel_embeds_poster_only_when_available(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active

    # Only "Has Free Ad-Supported" was given poster_image bytes.
    assert len(ws._images) == 1

    poster_row = _row_by_title(ws, "Has Free Ad-Supported")[0].row
    image = ws._images[0]
    assert image.anchor._from.row == poster_row - 1  # openpyxl anchors are 0-indexed
    assert image.anchor._from.col == POSTER_COL
