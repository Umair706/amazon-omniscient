"""Sub-niche detection service — detects broad keywords and clusters products into sub-niches."""

import logging
import math
import re
from collections import Counter

from app.llm.base_client import EXPERT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# Stop words to exclude from title diversity analysis
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "for", "in", "on", "of", "to", "with",
    "is", "it", "by", "at", "as", "from", "that", "this", "set", "pack",
    "pcs", "pieces", "inch", "cm", "mm", "new", "free", "shipping",
})


class SubNicheService:
    """Detects when a keyword is too broad and clusters products into sub-niches."""

    def __init__(self, llm_client=None):
        self.llm = llm_client

    def detect_heterogeneity(self, products: list[dict]) -> dict:
        """Algorithmic check for keyword broadness -- no LLM needed.

        Returns
        -------
        dict
            {
                "is_broad": bool,
                "price_cv": float,          # coefficient of variation
                "title_diversity": float,   # unique significant words / total
                "product_count": int,
            }
        """
        prices = [p["price"] for p in products if p.get("price") and p["price"] > 0]
        titles = [p.get("title", "") for p in products if p.get("title")]

        product_count = len(products)
        price_cv = 0.0
        title_diversity = 0.0

        # Price coefficient of variation
        if len(prices) >= 2:
            mean_price = sum(prices) / len(prices)
            if mean_price > 0:
                variance = sum((p - mean_price) ** 2 for p in prices) / len(prices)
                std_dev = math.sqrt(variance)
                price_cv = round(std_dev / mean_price, 3)

        # Title word diversity: ratio of unique significant words to total
        if titles:
            all_words: list[str] = []
            for title in titles:
                words = re.findall(r"[a-z]+", title.lower())
                significant = [w for w in words if w not in _STOP_WORDS and len(w) > 2]
                all_words.extend(significant)

            if all_words:
                title_diversity = round(len(set(all_words)) / len(all_words), 3)

        # Criteria for "broad":
        #   - Price CV > 0.6 OR title diversity > 0.7
        #   - AND at least 15 products scraped
        is_broad = (
            product_count >= 15
            and (price_cv > 0.6 or title_diversity > 0.7)
        )

        return {
            "is_broad": is_broad,
            "price_cv": price_cv,
            "title_diversity": title_diversity,
            "product_count": product_count,
        }

    async def cluster_sub_niches(
        self, keyword: str, products: list[dict]
    ) -> list[dict]:
        """Use LLM to group products into 3-6 coherent sub-niches.

        Parameters
        ----------
        keyword : str
            The original search keyword.
        products : list[dict]
            Scraped products with at least ``asin``, ``title``, ``price``.

        Returns
        -------
        list[dict]
            Each dict: {
                "label": str,
                "description": str,
                "asin_list": list[str],
                "avg_price": float,
                "product_count": int,
            }
        """
        if not self.llm:
            logger.warning("LLM client not available -- cannot cluster sub-niches")
            return []

        # Build compact product list for the prompt
        product_lines = []
        for p in products:
            asin = p.get("asin", "?")
            title = (p.get("title") or "")[:80]
            price = p.get("price", 0)
            product_lines.append(f"- {asin}: ${price:.2f} | {title}")

        products_text = "\n".join(product_lines)

        prompt = f"""The user searched for "{keyword}" and got products spanning multiple categories. Group these into 3-6 coherent sub-niches based on actual competitive sets — products that a buyer would compare against each other.

PRODUCTS:
{products_text}

GROUPING RULES:
- Group by actual competitive set: products a buyer would compare against each other when shopping. Same use case, similar price tier, similar form factor.
- Do NOT group by superficial similarity (e.g., don't group all "stainless steel" items together if they serve different purposes).
- Price tier is a strong signal: a $5 product and a $50 product in the same category are NOT in the same competitive set.
- Each sub-niche should represent a distinct buying decision.

Return a JSON array. Each element:
{{
    "label": "<Short descriptive name, e.g. 'Gold Chain Necklaces'>",
    "description": "<1-2 sentence description of this sub-niche and what makes it a distinct competitive set>",
    "asin_list": ["<ASIN1>", "<ASIN2>", ...],
    "avg_price": <average price of products in this group>,
    "product_count": <number of products>
}}

Rules:
- Every product ASIN must appear in exactly one sub-niche
- Each sub-niche must have at least 3 products
- Labels should be specific and descriptive
- Sort sub-niches by product_count descending
- Return ONLY the JSON array, no other text"""

        try:
            result = await self.llm.generate_json(prompt, max_tokens=4096, system_message=EXPERT_SYSTEM_PROMPT)

            # Validate and clean up the result
            if not isinstance(result, list):
                logger.warning("LLM returned non-list for sub-niche clustering")
                return []

            valid_clusters: list[dict] = []
            for cluster in result:
                if not isinstance(cluster, dict):
                    continue
                if not cluster.get("label") or not cluster.get("asin_list"):
                    continue
                # Ensure numeric fields
                cluster["avg_price"] = float(cluster.get("avg_price", 0))
                cluster["product_count"] = len(cluster["asin_list"])
                valid_clusters.append(cluster)

            # Sort by product_count descending
            valid_clusters.sort(key=lambda c: c["product_count"], reverse=True)

            logger.info(
                "Clustered %d products into %d sub-niches for '%s'",
                len(products),
                len(valid_clusters),
                keyword,
            )
            return valid_clusters

        except Exception as e:
            logger.warning("Sub-niche clustering failed: %s", e)
            return []
