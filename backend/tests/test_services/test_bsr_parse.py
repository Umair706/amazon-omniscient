from app.services.scraper_service import ScraperService

DETAILS = "Best Sellers Rank #2,345 in Home & Kitchen (See Top 100 in Home & Kitchen) #12 in Garlic Presses"


def test_parse_bsr_text_extracts_main_and_sub():
    parsed = ScraperService.parse_bsr_text(DETAILS)
    assert parsed == {
        "current_bsr": 2345, "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 12, "subcategory_name": "Garlic Presses",
    }


def test_parse_bsr_text_handles_missing():
    assert ScraperService.parse_bsr_text("") == {
        "current_bsr": None, "bsr_category": None, "current_subcategory_bsr": None, "subcategory_name": None,
    }
