from openpyxl import load_workbook

from src.excel_writer import HEADERS, TIER_STYLE, write_excel
from src.models import WatchlistTitle, YouTubeMatch


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
        if row[0].value == title_text:
            return [c.value for c in row]
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

    free_row = next(
        r for r in ws.iter_rows(min_row=2) if r[0].value == "Has Free Ad-Supported"
    )[0].row
    not_found_row = next(
        r for r in ws.iter_rows(min_row=2) if r[0].value == "Totally Unfound Title"
    )[0].row

    assert free_divider_row < free_row < not_found_divider_row < not_found_row


def test_write_excel_not_found_shows_not_found_label(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active

    row = _row_by_title(ws, "Totally Unfound Title")
    assert row[2] == "Not found"  # Subscription Services
    assert row[3] == "Not found"  # Rent/Buy
    assert row[4] == "Not found"  # Free (Ad-Supported)


def test_write_excel_row_values_and_hyperlink(tmp_path):
    titles = _make_titles()
    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active

    row = next(r for r in ws.iter_rows(min_row=2) if r[0].value == "Has Free Ad-Supported")
    assert row[2].value == "Netflix"
    assert row[3].value == "Amazon Video"
    assert row[4].value == "Tubi"
    assert row[0].hyperlink.target == "https://www.imdb.com/title/tt1/"
