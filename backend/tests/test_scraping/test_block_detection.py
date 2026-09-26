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
