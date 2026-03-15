"""Per-product supplier matching on 1688.com with LLM match scoring."""

import logging

from app.llm.base_client import BaseLLMClient
from app.services.supplier_scraper import SupplierScraper

logger = logging.getLogger(__name__)


class SupplierMatchService:
    """Finds per-product supplier matches on 1688.com."""

    def __init__(
        self,
        llm_client: BaseLLMClient,
        supplier_scraper: SupplierScraper | None = None,
    ):
        self.llm = llm_client
        self.scraper = supplier_scraper or SupplierScraper()

    async def find_matches_for_products(
        self,
        products: list[dict],
        max_suppliers_per_product: int = 3,
    ) -> list[dict]:
        """
        For each product, search 1688 with the product title (translated to Chinese),
        then use LLM to verify match quality.

        Returns list of per-product match results:
        [
            {
                "asin": "B0ABC...",
                "product_title": "...",
                "matched_suppliers": [
                    {
                        "supplier_name": "...",
                        "product_title": "...",
                        "match_score": 95,
                        "match_reasoning": "...",
                        "price_min_usd": 3.50,
                        "price_max_usd": 5.20,
                        "moq": 100,
                        "product_url": "https://detail.1688.com/...",
                        "image_url": "...",
                        ...
                    }
                ]
            }
        ]
        """
        results = []

        for product in products:
            asin = product.get("asin", "")
            title = product.get("title", "")
            if not title:
                results.append({
                    "asin": asin,
                    "product_title": title,
                    "matched_suppliers": [],
                })
                continue

            try:
                match_result = await self._match_single_product(
                    product, max_suppliers_per_product
                )
                results.append(match_result)
            except Exception as e:
                logger.warning("Supplier matching failed for %s: %s", asin, e)
                results.append({
                    "asin": asin,
                    "product_title": title,
                    "matched_suppliers": [],
                })

        return results

    async def _match_single_product(
        self, product: dict, max_suppliers: int
    ) -> dict:
        """Search 1688 for a single product and score matches."""
        asin = product.get("asin", "")
        title = product.get("title", "")

        # Translate title to Chinese for 1688 search
        chinese_query = await self._translate_title_to_chinese(title)

        # Search 1688 with the translated query
        try:
            supplier_listings = await self.scraper.search_suppliers(
                chinese_query, max_results=8
            )
        except Exception as e:
            logger.warning("1688 search failed for '%s': %s", chinese_query, e)
            supplier_listings = []

        if not supplier_listings:
            return {
                "asin": asin,
                "product_title": title,
                "matched_suppliers": [],
            }

        # Batch score all supplier candidates in a single LLM call
        scored = await self._batch_score_matches(product, supplier_listings)

        # Filter to match_score >= 85 and sort by score descending
        good_matches = [
            s for s in scored if s.get("match_score", 0) >= 85
        ]
        good_matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)

        return {
            "asin": asin,
            "product_title": title,
            "matched_suppliers": good_matches[:max_suppliers],
        }

    async def _translate_title_to_chinese(self, title: str) -> str:
        """Use LLM to translate a product title to Chinese for 1688 search."""
        prompt = f"""Translate this Amazon product title to a concise Chinese search query suitable for searching on 1688.com (Chinese wholesale marketplace).

Product title: {title}

Rules:
- Extract the core product type and key attributes
- Remove brand names, marketing language, and Amazon-specific phrasing
- Keep it concise (5-15 Chinese characters ideal)
- Return ONLY the Chinese text, nothing else"""

        try:
            result = await self.llm.generate(prompt, max_tokens=200)
            return result.strip().strip('"').strip("'")
        except Exception as e:
            logger.warning("Title translation failed, using original: %s", e)
            return title

    async def _batch_score_matches(
        self, amazon_product: dict, supplier_listings: list[dict]
    ) -> list[dict]:
        """Score all supplier candidates against an Amazon product in one LLM call."""
        title = amazon_product.get("title", "")
        price = amazon_product.get("price", "N/A")

        # Build supplier listing descriptions
        listing_descriptions = []
        for i, s in enumerate(supplier_listings):
            listing_descriptions.append(
                f"Supplier {i + 1}:\n"
                f"  - Title: {s.get('product_title', s.get('product_name', 'N/A'))}\n"
                f"  - Supplier: {s.get('supplier_name', s.get('shop_name', 'N/A'))}\n"
                f"  - Price: ¥{s.get('price_min', 'N/A')}-¥{s.get('price_max', 'N/A')}\n"
                f"  - MOQ: {s.get('moq', 'N/A')}\n"
                f"  - Location: {s.get('location', 'N/A')}\n"
                f"  - Transaction count: {s.get('transaction_count', 'N/A')}"
            )

        suppliers_text = "\n\n".join(listing_descriptions)

        prompt = f"""Compare this Amazon product with each 1688.com supplier listing below.
Score how likely it is that each supplier listing is the SAME or nearly identical product (0-100).

Amazon Product:
- Title: {title}
- Price: ${price}

1688 Supplier Listings:
{suppliers_text}

Scoring guide:
90-100: Same product (same materials, same design, same function)
70-89: Very similar product (minor differences in size/color/variant)
50-69: Same category but different design/quality
0-49: Different product

Return a JSON array with one entry per supplier:
[
    {{"supplier_index": 1, "match_score": <0-100>, "match_reasoning": "<brief explanation>"}},
    ...
]"""

        try:
            scores = await self.llm.generate_json(prompt, max_tokens=4096)
        except Exception as e:
            logger.warning("Batch match scoring failed: %s", e)
            return []

        if not isinstance(scores, list):
            return []

        # Merge scores back into supplier data
        scored_suppliers = []
        for score_entry in scores:
            idx = score_entry.get("supplier_index", 0) - 1
            if 0 <= idx < len(supplier_listings):
                supplier = dict(supplier_listings[idx])
                supplier["match_score"] = score_entry.get("match_score", 0)
                supplier["match_reasoning"] = score_entry.get("match_reasoning", "")

                # Normalize field names for consistency
                _CNY_TO_USD = 7.2
                price_min = supplier.get("price_min")
                price_max = supplier.get("price_max")
                supplier["price_min_usd"] = round(price_min / _CNY_TO_USD, 2) if price_min else None
                supplier["price_max_usd"] = round(price_max / _CNY_TO_USD, 2) if price_max else None

                scored_suppliers.append(supplier)

        return scored_suppliers
