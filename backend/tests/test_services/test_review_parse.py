from app.services.review_text import parse_helpful_votes, parse_review_date

# Strings captured 2026-09-26 from review cards on amazon.com.au/dp/B00HEZ888K.
AU_REVIEW_DATE = "Reviewed in Australia on 28 July 2026"
AU_SINGLE_DIGIT_DAY = "Reviewed in Australia on 9 July 2026"
FOREIGN_REVIEW_DATE = "Reviewed in the United Arab Emirates on 12 August 2026"
AU_ONE_PERSON_HELPFUL = "One person found this helpful"

# The older US template writes the month first.
US_REVIEW_DATE = "Reviewed in the United States on March 12, 2026"


def test_parse_review_date_reads_day_first_dates():
    assert parse_review_date(AU_REVIEW_DATE) == "2026-07-28"
    assert parse_review_date(AU_SINGLE_DIGIT_DAY) == "2026-07-09"


def test_parse_review_date_reads_reviews_from_other_countries():
    assert parse_review_date(FOREIGN_REVIEW_DATE) == "2026-08-12"


def test_parse_review_date_reads_month_first_dates():
    assert parse_review_date(US_REVIEW_DATE) == "2026-03-12"


def test_parse_review_date_returns_none_for_text_without_a_date():
    assert parse_review_date("Reviewed in Australia") is None
    assert parse_review_date("") is None
    assert parse_review_date(None) is None


def test_parse_helpful_votes_reads_one_person():
    assert parse_helpful_votes(AU_ONE_PERSON_HELPFUL) == 1


def test_parse_helpful_votes_reads_counts_with_commas():
    assert parse_helpful_votes("12 people found this helpful") == 12
    assert parse_helpful_votes("1,234 people found this helpful") == 1234


def test_parse_helpful_votes_is_zero_without_a_statement():
    assert parse_helpful_votes("") == 0
    assert parse_helpful_votes(None) == 0
