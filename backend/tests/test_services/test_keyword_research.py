"""Seed-root expansion for autocomplete keyword discovery.

A long specific phrase returns almost no autocomplete suggestions on its own, so
we also query its shorter word-prefixes. These tests pin that root list.
"""

from app.services.keyword_research import KeywordResearchService


def test_long_phrase_expands_to_shorter_roots():
    # "bean bags for adults" alone yields nothing; "bean bags" yields many.
    roots = KeywordResearchService._seed_roots("bean bags for adults")
    assert roots == ["bean bags for adults", "bean bags for", "bean bags"]


def test_three_word_seed_stops_at_two_words():
    roots = KeywordResearchService._seed_roots("wireless earbuds case")
    assert roots == ["wireless earbuds case", "wireless earbuds"]


def test_two_word_seed_is_not_shortened():
    # Never drop below two words — a one-word root is too broad and off-topic.
    assert KeywordResearchService._seed_roots("bean bags") == ["bean bags"]


def test_one_word_seed_is_returned_as_is():
    assert KeywordResearchService._seed_roots("earbuds") == ["earbuds"]


def test_seed_is_always_first_root():
    # The exact seed must come first so it gets depth 0 (highest volume signal).
    roots = KeywordResearchService._seed_roots("stainless steel water bottle")
    assert roots[0] == "stainless steel water bottle"
