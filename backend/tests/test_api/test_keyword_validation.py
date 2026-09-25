import pytest
from pydantic import ValidationError

from app.api.jobs import AnalyzeKeywordRequest


def test_keyword_is_trimmed_and_control_chars_removed():
    req = AnalyzeKeywordRequest(keyword="  garlic\npress\t ")
    assert req.keyword == "garlic press"


def test_whitespace_only_keyword_rejected():
    with pytest.raises(ValidationError, match="keyword must not be blank"):
        AnalyzeKeywordRequest(keyword="   ")


def test_keyword_too_long_rejected():
    with pytest.raises(ValidationError):
        AnalyzeKeywordRequest(keyword="x" * 101)
