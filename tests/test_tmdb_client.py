from unittest.mock import MagicMock

import pytest

from src.tmdb_client import TMDbClient, TMDbError


def _mock_response(status_code=200, json_data=None, text=""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.text = text
    return resp


def test_find_by_imdb_id_prefers_movie_for_movie_type():
    session = MagicMock()
    session.get.return_value = _mock_response(
        json_data={"movie_results": [{"id": 680}], "tv_results": []}
    )
    client = TMDbClient(session, "key")
    assert client.find_by_imdb_id("tt0110912", "movie") == (680, "movie")


def test_find_by_imdb_id_prefers_tv_for_tv_type():
    session = MagicMock()
    session.get.return_value = _mock_response(
        json_data={"movie_results": [], "tv_results": [{"id": 1399}]}
    )
    client = TMDbClient(session, "key")
    assert client.find_by_imdb_id("tt0944947", "tvSeries") == (1399, "tv")


def test_find_by_imdb_id_no_match_returns_none():
    session = MagicMock()
    session.get.return_value = _mock_response(json_data={"movie_results": [], "tv_results": []})
    client = TMDbClient(session, "key")
    assert client.find_by_imdb_id("tt9999999", "movie") is None


def test_get_watch_providers_splits_categories():
    session = MagicMock()
    session.get.return_value = _mock_response(
        json_data={
            "results": {
                "US": {
                    "flatrate": [{"provider_name": "Netflix"}],
                    "rent": [{"provider_name": "Amazon Video"}],
                    "buy": [
                        {"provider_name": "Amazon Video"},
                        {"provider_name": "Apple TV"},
                    ],
                    "ads": [{"provider_name": "Tubi"}],
                    "free": [{"provider_name": "Pluto TV"}],
                }
            }
        }
    )
    client = TMDbClient(session, "key")
    result = client.get_watch_providers(680, "movie")
    assert result.subscription == ["Netflix"]
    assert result.rent_buy == ["Amazon Video", "Apple TV"]
    assert result.free_ad_supported == ["Pluto TV", "Tubi"]


def test_get_watch_providers_missing_region_is_empty():
    session = MagicMock()
    session.get.return_value = _mock_response(json_data={"results": {}})
    client = TMDbClient(session, "key")
    result = client.get_watch_providers(680, "movie")
    assert result.subscription == []
    assert result.rent_buy == []
    assert result.free_ad_supported == []


def test_error_status_raises():
    session = MagicMock()
    session.get.return_value = _mock_response(status_code=500, text="server error")
    client = TMDbClient(session, "key")
    with pytest.raises(TMDbError):
        client.find_by_imdb_id("tt0110912", "movie")
