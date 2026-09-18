import json
from pathlib import Path

import pytest

from src.imdb_scraper import ScraperError, _extract_next_data, _parse_page

FIXTURE = Path(__file__).parent / "fixtures" / "sample_next_data.json"


def _html_with_next_data(payload: dict) -> str:
    return (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
        "</body></html>"
    )


def test_extract_next_data_success():
    payload = json.loads(FIXTURE.read_text())
    html = _html_with_next_data(payload)
    data = _extract_next_data(html, "http://example.com")
    assert data == payload


def test_extract_next_data_missing_script_raises():
    with pytest.raises(ScraperError):
        _extract_next_data("<html><body>no script here</body></html>", "http://example.com")


def test_extract_next_data_invalid_json_raises():
    html = '<script id="__NEXT_DATA__" type="application/json">{not json}</script>'
    with pytest.raises(ScraperError):
        _extract_next_data(html, "http://example.com")


def test_parse_page_extracts_titles():
    payload = json.loads(FIXTURE.read_text())
    titles, page_info, total = _parse_page(payload)

    assert total == 2
    assert page_info["hasNextPage"] is False
    assert len(titles) == 2

    pulp = titles[0]
    assert pulp.imdb_id == "tt0110912"
    assert pulp.title == "Pulp Fiction"
    assert pulp.year == 1994
    assert pulp.title_type == "movie"
    assert pulp.poster_url == "https://example.com/pulp.jpg"


def test_parse_page_missing_key_raises():
    with pytest.raises(ScraperError):
        _parse_page({"props": {"pageProps": {}}})


def test_parse_page_malformed_item_raises():
    payload = {
        "props": {
            "pageProps": {
                "mainColumnData": {
                    "list": {
                        "titleListItemSearch": {
                            "total": 1,
                            "pageInfo": {"hasNextPage": False},
                            "edges": [
                                {
                                    "listItem": {
                                        "id": None,
                                        "titleText": {"text": "Bad"},
                                        "titleType": {"id": "movie"},
                                    }
                                }
                            ],
                        }
                    }
                }
            }
        }
    }
    with pytest.raises(ScraperError):
        _parse_page(payload)
