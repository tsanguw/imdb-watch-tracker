import io
from unittest.mock import MagicMock

from PIL import Image as PILImage

from src.poster_fetcher import POSTER_SIZE, fetch_poster_image


def _fake_poster_bytes(width=185, height=278) -> bytes:
    image = PILImage.new("RGB", (width, height), color=(120, 40, 200))
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _mock_response(status_code=200, content=b""):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    return resp


def test_fetch_poster_image_resizes_and_returns_png_bytes():
    session = MagicMock()
    session.get.return_value = _mock_response(content=_fake_poster_bytes())

    result = fetch_poster_image("https://image.tmdb.org/t/p/w185/fake.jpg", session)

    assert result is not None
    image = PILImage.open(io.BytesIO(result))
    assert image.format == "PNG"
    assert image.width <= POSTER_SIZE[0]
    assert image.height <= POSTER_SIZE[1]


def test_fetch_poster_image_returns_none_on_http_error():
    session = MagicMock()
    session.get.return_value = _mock_response(status_code=404)

    assert fetch_poster_image("https://image.tmdb.org/t/p/w185/missing.jpg", session) is None


def test_fetch_poster_image_returns_none_on_bad_image_bytes():
    session = MagicMock()
    session.get.return_value = _mock_response(content=b"not an image")

    assert fetch_poster_image("https://image.tmdb.org/t/p/w185/broken.jpg", session) is None
