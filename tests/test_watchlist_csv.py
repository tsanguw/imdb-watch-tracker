from pathlib import Path

import pytest

from src.watchlist_csv import WatchlistCSVError, load_watchlist_csv

FIXTURE = Path(__file__).parent / "fixtures" / "sample_watchlist_export.csv"


def test_load_watchlist_csv_success():
    titles = load_watchlist_csv(str(FIXTURE))
    assert len(titles) == 2

    pulp = titles[0]
    assert pulp.imdb_id == "tt0110912"
    assert pulp.title == "Pulp Fiction"
    assert pulp.year == 1994
    assert pulp.title_type == "movie"

    got = titles[1]
    assert got.imdb_id == "tt0944947"
    assert got.title == "Game of Thrones"
    assert got.year == 2011
    assert got.title_type == "tvSeries"


def test_missing_file_raises():
    with pytest.raises(WatchlistCSVError, match="not found"):
        load_watchlist_csv("does/not/exist.csv")


def test_missing_required_columns_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text("Title,Year\nSome Movie,2020\n", encoding="utf-8")
    with pytest.raises(WatchlistCSVError, match="missing expected column"):
        load_watchlist_csv(str(path))


def test_malformed_row_raises(tmp_path):
    path = tmp_path / "bad.csv"
    path.write_text(
        "Const,Title,Title Type,Year\n,Some Movie,movie,2020\n",
        encoding="utf-8",
    )
    with pytest.raises(WatchlistCSVError, match="malformed"):
        load_watchlist_csv(str(path))


def test_empty_watchlist_raises(tmp_path):
    path = tmp_path / "empty.csv"
    path.write_text("Const,Title,Title Type,Year\n", encoding="utf-8")
    with pytest.raises(WatchlistCSVError, match="no titles"):
        load_watchlist_csv(str(path))


def test_duplicate_ids_are_deduped(tmp_path):
    path = tmp_path / "dupes.csv"
    path.write_text(
        "Const,Title,Title Type,Year\n"
        "tt0110912,Pulp Fiction,movie,1994\n"
        "tt0110912,Pulp Fiction,movie,1994\n",
        encoding="utf-8",
    )
    titles = load_watchlist_csv(str(path))
    assert len(titles) == 1


def test_year_falls_back_to_release_date(tmp_path):
    path = tmp_path / "release_date.csv"
    path.write_text(
        "Const,Title,Title Type,Release Date\n"
        "tt0110912,Pulp Fiction,movie,1994-10-14\n",
        encoding="utf-8",
    )
    titles = load_watchlist_csv(str(path))
    assert titles[0].year == 1994
