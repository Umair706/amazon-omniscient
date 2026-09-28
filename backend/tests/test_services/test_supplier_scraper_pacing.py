from unittest.mock import AsyncMock

from app.scraping.pacing import pacer_for
from app.services.supplier_scraper import SupplierScraper


def test_supplier_scraper_defaults_to_the_1688_pacer():
    assert SupplierScraper().pacer is pacer_for("1688")


def test_supplier_scraper_accepts_injected_pacer():
    custom = AsyncMock()
    assert SupplierScraper(pacer=custom).pacer is custom
