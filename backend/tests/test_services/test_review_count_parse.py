import pytest

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
