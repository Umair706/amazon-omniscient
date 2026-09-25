from app.services.scraper_service import ScraperService

DETAILS = "Best Sellers Rank #2,345 in Home & Kitchen (See Top 100 in Home & Kitchen) #12 in Garlic Presses"

# Real details-block innerText() puts each "#N in Category" pair on its own
# line, with more text (e.g. "Customer Reviews") following the last one.
MULTILINE_DETAILS = (
    "Best Sellers Rank #2,345 in Home & Kitchen (See Top 100 in Home & Kitchen)\n"
    "#12 in Garlic Presses\n"
    "Customer Reviews 4.5 out of 5"
)

# Category names can contain digits, commas, and ampersands.
DIGIT_COMMA_DETAILS = (
    "#1,234 in Arts, Crafts & Sewing (See Top 100 in Arts, Crafts & Sewing) "
    "#7 in 3D Printing Supplies"
)


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


def test_parse_bsr_text_handles_multiline_rows():
    parsed = ScraperService.parse_bsr_text(MULTILINE_DETAILS)
    assert parsed == {
        "current_bsr": 2345, "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 12, "subcategory_name": "Garlic Presses",
    }


def test_parse_bsr_text_handles_digits_and_commas_in_category():
    parsed = ScraperService.parse_bsr_text(DIGIT_COMMA_DETAILS)
    assert parsed == {
        "current_bsr": 1234, "bsr_category": "Arts, Crafts & Sewing",
        "current_subcategory_bsr": 7, "subcategory_name": "3D Printing Supplies",
    }


# Captured 2026-09-26 from amazon.com.au/dp/B00HEZ888K: text_content() of the
# "Best Sellers Rank" row in #prodDetails. The 2026 template drops the "#"
# prefix, and text_content() has no line break between the two ranks.
AU_2026_BSR_ROW = "  118 in Kitchen & Dining (See Top 100 in Kitchen & Dining)  1 in Garlic Presses  "

# The sub-category rank sits right after the aside on the same line.
HASHLESS_SAME_LINE = "2,345 in Home & Kitchen (See Top 100 in Home & Kitchen) 12 in Garlic Presses"

# No aside at all: only the next "<number> in" marks where the first category ends.
HASHLESS_NO_ASIDE = "Best Sellers Rank 2,345 in Home & Kitchen 12 in Garlic Presses"

HASHLESS_DIGIT_CATEGORY = (
    "1,234 in Arts, Crafts & Sewing (See Top 100 in Arts, Crafts & Sewing) 7 in 3D Printing Supplies"
)


def test_parse_bsr_text_reads_the_2026_template_without_hash():
    parsed = ScraperService.parse_bsr_text(AU_2026_BSR_ROW)
    assert parsed == {
        "current_bsr": 118, "bsr_category": "Kitchen & Dining",
        "current_subcategory_bsr": 1, "subcategory_name": "Garlic Presses",
    }


def test_parse_bsr_text_splits_hashless_ranks_on_the_same_line():
    parsed = ScraperService.parse_bsr_text(HASHLESS_SAME_LINE)
    assert parsed == {
        "current_bsr": 2345, "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 12, "subcategory_name": "Garlic Presses",
    }


def test_parse_bsr_text_splits_hashless_ranks_without_an_aside():
    parsed = ScraperService.parse_bsr_text(HASHLESS_NO_ASIDE)
    assert parsed == {
        "current_bsr": 2345, "bsr_category": "Home & Kitchen",
        "current_subcategory_bsr": 12, "subcategory_name": "Garlic Presses",
    }


def test_parse_bsr_text_keeps_digits_in_a_hashless_category():
    parsed = ScraperService.parse_bsr_text(HASHLESS_DIGIT_CATEGORY)
    assert parsed == {
        "current_bsr": 1234, "bsr_category": "Arts, Crafts & Sewing",
        "current_subcategory_bsr": 7, "subcategory_name": "3D Printing Supplies",
    }
