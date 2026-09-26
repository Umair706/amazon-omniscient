from unittest.mock import AsyncMock

import pytest

from app.core.proxy_manager import ProxyManager
from app.services.scraper_service import ScraperService

# Texts captured from amazon.com.au on 2026-09-25.


@pytest.mark.parametrize("text, expected", [
    ("(38,907)", 38907),          # product page #acrCustomerReviewText
    ("38,907 reviews", 38907),    # its aria-label
    ("6,602 ratings", 6602),      # search result ratings-link aria-label
    ("(33)", 33),
    ("(6.6K)", 6600),             # search result visible text, abbreviated
    ("1.2k ratings", 1200),
])
def test_review_count_is_read_from_count_text(text, expected):
    assert ScraperService.parse_review_count_text(text) == expected


@pytest.mark.parametrize("text", ["4.5 out of 5 stars", "4.6 Out of 5", None, "", "(0)", "no reviews"])
def test_star_ratings_and_empty_text_are_not_review_counts(text):
    assert ScraperService.parse_review_count_text(text) is None


async def test_extract_review_count_falls_back_to_the_second_selector(monkeypatch):
    # WHY: "#acrCustomerReviewCount" is missing on some templates, so
    # _extract_review_count must try "#acrCustomerReviewText" next.
    scraper = ScraperService(proxy_manager=ProxyManager(provider="none"))
    monkeypatch.setattr(scraper, "_safe_text", AsyncMock(side_effect=[None, "1,543 ratings"]))

    assert await scraper._extract_review_count(page=None) == 1543
