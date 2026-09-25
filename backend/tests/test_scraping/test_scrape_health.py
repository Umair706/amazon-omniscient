"""summarise_scrape_counts: pure aggregation logic behind GET /niches/scrape-health."""

from app.scraping.health import summarise_scrape_counts


def test_groups_rows_by_site_and_verdict():
    rows = [("amazon", "ok", 42), ("amazon", "captcha", 3), ("1688", "ok", 7)]
    assert summarise_scrape_counts(rows) == {
        "counts": [
            {"site": "amazon", "verdict": "ok", "count": 42},
            {"site": "amazon", "verdict": "captcha", "count": 3},
            {"site": "1688", "verdict": "ok", "count": 7},
        ]
    }


def test_no_rows_gives_empty_counts():
    assert summarise_scrape_counts([]) == {"counts": []}
