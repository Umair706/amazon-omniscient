from app.core.marketplace import get_marketplace
from app.scraping.persona import build_persona


def test_persona_ua_matches_platform_and_browser_version():
    p = build_persona("124.0.6367.60", get_marketplace("AU"))
    assert "Chrome/124.0.0.0" in p.user_agent
    assert (("Windows" in p.user_agent) == (p.platform == "Win32"))
    assert p.locale == "en-AU" and p.timezone_id == "Australia/Sydney"
    assert p.accept_language.startswith("en-AU")
    assert 1280 <= p.viewport["width"] <= 1920


def test_init_script_sets_matching_platform():
    p = build_persona("124.0.6367.60", get_marketplace("US"))
    assert f"'{p.platform}'" in p.init_script()
    assert "webdriver" in p.init_script()
