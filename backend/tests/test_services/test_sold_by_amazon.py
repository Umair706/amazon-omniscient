from app.services.scraper_service import ScraperService


def test_classic_merchant_line_naming_amazon_counts():
    assert ScraperService.is_sold_by_amazon("Ships from and sold by Amazon.com.au.")


def test_tabular_buy_box_with_label_and_name_on_separate_lines_counts():
    assert ScraperService.is_sold_by_amazon("Ships from\nAmazon\nSold by\nAmazon")


def test_2026_shipper_seller_layout_counts():
    assert ScraperService.is_sold_by_amazon("Shipper / Seller\nAmazon AU")


def test_third_party_seller_does_not_count():
    assert not ScraperService.is_sold_by_amazon("Ships from Amazon\nSold by Kitchen Gadgets Co")
    assert not ScraperService.is_sold_by_amazon("Shipper / Seller\nKitchen Gadgets Co")


def test_missing_merchant_text_does_not_count():
    assert not ScraperService.is_sold_by_amazon(None)
    assert not ScraperService.is_sold_by_amazon("")
