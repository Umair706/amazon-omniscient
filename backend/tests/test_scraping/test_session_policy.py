from unittest.mock import AsyncMock, MagicMock

import pytest

from app.scraping.session import BrowserSession, should_block_request


def test_blocks_images_media_fonts():
    assert should_block_request("image", "https://m.media-amazon.com/images/I/x.jpg")
    assert should_block_request("media", "https://x/video.mp4")
    assert should_block_request("font", "https://x/f.woff2")


def test_allows_documents_scripts_xhr():
    assert not should_block_request("document", "https://www.amazon.com/dp/B0A")
    assert not should_block_request("script", "https://www.amazon.com/x.js")
    assert not should_block_request("xhr", "https://www.amazon.com/api")


async def test_playwright_is_stopped_even_when_closing_the_browser_fails():
    session = BrowserSession(marketplace=MagicMock(), proxy_manager=MagicMock())
    session._pw = MagicMock(stop=AsyncMock())
    session._close = AsyncMock(side_effect=RuntimeError("browser already gone"))
    with pytest.raises(RuntimeError):
        await session.__aexit__(None, None, None)
    session._pw.stop.assert_awaited_once()


def test_never_blocks_captcha_image():
    # WHY: if we ever add a solver it needs the challenge image.
    assert not should_block_request("image", "https://images-na.ssl-images-amazon.com/captcha/abc.jpg")
