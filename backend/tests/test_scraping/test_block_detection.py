from app.scraping.block_detection import classify_page


def test_captcha_page():
    assert classify_page(200, "Amazon.com", "Enter the characters you see below ... api-services-support@amazon.com", False) == "captcha"


def test_robot_check_title():
    assert classify_page(200, "Robot Check", "", False) == "captcha"


def test_server_error():
    assert classify_page(503, "Sorry! Something went wrong!", "", False) == "server_error"


def test_soft_block_when_expected_content_missing():
    assert classify_page(200, "Amazon.com : garlic press", "Results", False) == "soft_block"


def test_ok():
    assert classify_page(200, "Amazon.com : garlic press", "Results", True) == "ok"


def test_is_on_marketplace_accepts_the_domain_and_its_subdomains():
    from app.scraping.block_detection import is_on_marketplace

    assert is_on_marketplace("https://www.amazon.com/dp/B0A", "amazon.com")
    assert is_on_marketplace("https://amazon.com/s?k=x", "amazon.com")
    assert is_on_marketplace("https://www.amazon.com.au/dp/B0A", "amazon.com.au")


def test_is_on_marketplace_rejects_another_countrys_store():
    from app.scraping.block_detection import is_on_marketplace

    # amazon.com geo-redirects Australian visitors here; the page parses fine but is the wrong market.
    assert not is_on_marketplace("https://www.amazon.com.au/dp/B0A?ref_=mr_direct_us_au_au", "amazon.com")
    assert not is_on_marketplace("https://www.amazon.com/dp/B0A", "amazon.com.au")
    assert not is_on_marketplace("", "amazon.com")
