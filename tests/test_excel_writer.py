from openpyxl import load_workbook

from src.excel_writer import HEADERS, write_excel
from src.models import WatchlistTitle


def test_write_excel_basic(tmp_path):
    titles = [
        WatchlistTitle(
            imdb_id="tt0110912",
            title="Pulp Fiction",
            year=1994,
            title_type="movie",
            tmdb_found=True,
            subscription=["Netflix"],
            rent_buy=["Amazon Video"],
            free_ad_supported=[],
            last_checked="2026-01-01 00:00 UTC",
        ),
        WatchlistTitle(
            imdb_id="tt9999999",
            title="Some Obscure Title",
            year=2020,
            title_type="movie",
            tmdb_found=False,
            last_checked="2026-01-01 00:00 UTC",
        ),
    ]

    output_path = tmp_path / "watchlist.xlsx"
    write_excel(titles, str(output_path))

    wb = load_workbook(output_path)
    ws = wb.active
    header_row = [cell.value for cell in ws[1]]
    assert header_row == HEADERS

    row2 = [cell.value for cell in ws[2]]
    assert row2[0] == "Pulp Fiction"
    assert row2[2] == "Netflix"

    row3 = [cell.value for cell in ws[3]]
    assert row3[2] == "Not found"
