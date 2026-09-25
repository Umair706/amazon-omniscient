"""Pure parsers for the text Amazon shows on a review card (date line, helpful-vote line)."""

import re
from datetime import datetime

# The date comes after "on": "Reviewed in Australia on 28 July 2026".
_DATE_AFTER_ON = re.compile(r"\bon\s+(.+?)\s*$")

# WHY: AU/UK pages write the day first ("28 July 2026"); US pages write the
# month first ("March 12, 2026"). We try both.
_REVIEW_DATE_FORMATS = ("%d %B %Y", "%B %d, %Y")

_HELPFUL_COUNT = re.compile(r"([\d,]+)")

# Amazon spells out a single vote: "One person found this helpful".
_ONE_PERSON_MARKER = "one person"


def parse_review_date(date_line: str | None) -> str | None:
    """Return the review date as an ISO string ("2026-07-28"), or None if the line has no readable date."""
    if not date_line:
        return None
    match = _DATE_AFTER_ON.search(date_line)
    if not match:
        return None
    date_text = match.group(1)
    for date_format in _REVIEW_DATE_FORMATS:
        try:
            return datetime.strptime(date_text, date_format).date().isoformat()
        except ValueError:
            continue
    return None


def parse_helpful_votes(helpful_line: str | None) -> int:
    """Return how many people found the review helpful. 0 when there is no statement."""
    if not helpful_line:
        return 0
    if _ONE_PERSON_MARKER in helpful_line.lower():
        return 1
    match = _HELPFUL_COUNT.search(helpful_line)
    if not match:
        return 0
    return int(match.group(1).replace(",", ""))
