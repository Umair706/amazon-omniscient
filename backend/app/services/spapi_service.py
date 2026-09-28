"""Amazon SP-API service wrapper for product data, fees, and BSR."""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.core.exceptions import SPAPIError
from app.core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# SP-API throttles hard and returns 429 with a Retry-After header. We pace requests a
# little on the way out and back off (honouring Retry-After) on the way in, so the
# tracker never hammers a throttled endpoint with more 429s.
SPAPI_MIN_REQUEST_INTERVAL_SECONDS = 0.5
SPAPI_MAX_RETRIES = 3
SPAPI_MAX_BACKOFF_SECONDS = 30


def _retry_after_seconds(response: httpx.Response) -> int:
    """Seconds to wait from a 429's Retry-After header; 2s when absent or unparseable."""
    try:
        return max(1, int(response.headers.get("Retry-After", "2")))
    except (TypeError, ValueError):
        return 2

# SP-API endpoints (default; overridden per marketplace)
SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"
TOKEN_URL = "https://api.amazon.com/auth/o2/token"

# Catalog Items v2022-04-01 tags one image per product as the primary listing photo.
MAIN_IMAGE_VARIANT = "MAIN"


def _main_image_link(item: dict, marketplace_id: str) -> str | None:
    """Find this marketplace's MAIN product image link from a Catalog Items v2022-04-01 item.

    The API's top-level `images` field (not `summaries[].mainImage`, which doesn't exist
    in this API version) holds a list of images per marketplace, each tagged with a
    `variant` like "MAIN" or "PT01". Falls back to the first image if none is tagged MAIN,
    and to the legacy `summaries[].mainImage` shape as a last resort.
    """
    images_block = next((i for i in item.get("images", []) if i.get("marketplaceId") == marketplace_id), {})
    images = images_block.get("images", [])
    main_image = next((i for i in images if i.get("variant") == MAIN_IMAGE_VARIANT), None)
    if main_image is None and images:
        main_image = images[0]
    if main_image is not None:
        return main_image.get("link")

    summary = next((s for s in item.get("summaries", []) if s.get("marketplaceId") == marketplace_id), {})
    return (summary.get("mainImage") or {}).get("link")


def normalise_catalog_item(item: dict, marketplace_id: str) -> dict:
    """Map a Catalog Items v2022-04-01 item onto the dict shape ScraperService.scrape_search_results returns."""
    summary = next((s for s in item.get("summaries", []) if s.get("marketplaceId") == marketplace_id), {})
    ranks = next((r for r in item.get("salesRanks", []) if r.get("marketplaceId") == marketplace_id), {})
    main = (ranks.get("displayGroupRanks") or [{}])[0]
    sub = (ranks.get("classificationRanks") or [{}])[0]
    return {
        "asin": item.get("asin"),
        "title": summary.get("itemName"),
        "brand": summary.get("brand"),
        "image_url": _main_image_link(item, marketplace_id),
        "price": None, "rating": None, "review_count": None,
        "bsr": main.get("rank"), "bsr_category": main.get("title"),
        "current_subcategory_bsr": sub.get("rank"), "subcategory_name": sub.get("title"),
        "is_sponsored": False, "is_amazon_choice": False, "is_best_seller": False, "is_fba": None,
    }


class SPAPIService:
    """
    Amazon Selling Partner API service.

    Handles authentication (LWA token refresh), request signing,
    and provides methods for:
    1. Get catalog item (product details by ASIN)
    2. Get competitive pricing
    3. Get product fees estimate
    4. Get BSR/sales rank
    5. Search catalog items

    Supports multiple marketplaces via the marketplace parameter.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        aws_access_key: str | None = None,
        aws_secret_key: str | None = None,
        marketplace_id: str | None = None,
        marketplace: str = "US",
        rate_limiter: RateLimiter | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.rate_limiter = rate_limiter

        # Load marketplace config for endpoint and marketplace_id
        from app.core.marketplace import get_marketplace
        mp = get_marketplace(marketplace)
        self.marketplace_id = marketplace_id or mp.marketplace_id
        self._sp_api_base = mp.sp_api_endpoint

        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._http_client = httpx.AsyncClient(timeout=30.0)
        # Proactive client-side pacing: one request at a time, spaced by a minimum gap.
        self._request_lock = asyncio.Lock()
        self._last_request_at = 0.0

    async def close(self):
        """Close the HTTP client."""
        await self._http_client.aclose()

    # ------------------------------------------------------------------
    # Auth: LWA token refresh
    # ------------------------------------------------------------------
    async def _ensure_access_token(self) -> str:
        """Refresh the LWA access token if expired or missing."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._token_expires_at and now < self._token_expires_at:
            return self._access_token

        try:
            response = await self._http_client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
            self._access_token = data["access_token"]
            # Token usually valid for 3600 seconds; refresh 5 min early
            expires_in = data.get("expires_in", 3600)
            from datetime import timedelta
            self._token_expires_at = now + timedelta(seconds=expires_in - 300)
            return self._access_token
        except Exception as e:
            raise SPAPIError(f"Failed to refresh SP-API access token: {e}") from e

    # ------------------------------------------------------------------
    # HTTP request helper
    # ------------------------------------------------------------------
    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
        rate_limit_key: str = "spapi:default",
    ) -> dict:
        """Make an authenticated request to SP-API, pacing outbound and backing off on 429."""
        if self.rate_limiter:
            await self.rate_limiter.check_rate(rate_limit_key, max_requests=10, window_seconds=1)

        url = f"{self._sp_api_base}{path}"
        for attempt in range(SPAPI_MAX_RETRIES + 1):
            await self._pace()
            token = await self._ensure_access_token()
            headers = {
                "x-amz-access-token": token,
                "Content-Type": "application/json",
                "User-Agent": "Omniscient/1.0 (Language=Python)",
            }
            try:
                response = await self._http_client.request(
                    method=method, url=url, params=params, json=json_body, headers=headers,
                )
            except httpx.HTTPError as e:
                raise SPAPIError(f"SP-API request error: {e}") from e

            if response.status_code == 429:
                retry_after = min(_retry_after_seconds(response), SPAPI_MAX_BACKOFF_SECONDS)
                if attempt < SPAPI_MAX_RETRIES:
                    logger.warning(
                        "SP-API 429 on %s; backing off %ds (attempt %d/%d)",
                        path, retry_after, attempt + 1, SPAPI_MAX_RETRIES,
                    )
                    await asyncio.sleep(retry_after)
                    continue
                raise SPAPIError("SP-API rate limit exceeded after retries", retry_after=retry_after)

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise SPAPIError(
                    f"SP-API request failed ({e.response.status_code}): {e.response.text[:500]}"
                ) from e
            return response.json()

        # Unreachable: the loop either returns, continues, or raises. Guard for safety.
        raise SPAPIError("SP-API request exhausted retries")

    async def _pace(self) -> None:
        """Hold requests to at least SPAPI_MIN_REQUEST_INTERVAL_SECONDS apart, one at a time."""
        async with self._request_lock:
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < SPAPI_MIN_REQUEST_INTERVAL_SECONDS:
                await asyncio.sleep(SPAPI_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
            self._last_request_at = time.monotonic()

    # ------------------------------------------------------------------
    # 1. Get catalog item
    # ------------------------------------------------------------------
    async def get_catalog_item(self, asin: str) -> dict:
        """Get product details for a single ASIN from the Catalog Items API."""
        params = {
            "marketplaceIds": self.marketplace_id,
            "includedData": "attributes,dimensions,identifiers,images,productTypes,salesRanks,summaries",
        }
        data = await self._request(
            "GET",
            f"/catalog/2022-04-01/items/{asin}",
            params=params,
            rate_limit_key="spapi:catalog",
        )
        return data

    # ------------------------------------------------------------------
    # 2. Search catalog items by keyword
    # ------------------------------------------------------------------
    async def search_catalog_items(
        self,
        keywords: str,
        page_size: int = 20,
        page_token: str | None = None,
    ) -> dict:
        """Search the Amazon catalog by keywords."""
        params = {
            "marketplaceIds": self.marketplace_id,
            "keywords": keywords,
            "pageSize": page_size,
            "includedData": "attributes,dimensions,identifiers,images,salesRanks,summaries",
        }
        if page_token:
            params["pageToken"] = page_token

        data = await self._request(
            "GET",
            "/catalog/2022-04-01/items",
            params=params,
            rate_limit_key="spapi:catalog_search",
        )
        return data

    async def search_catalog_products(self, keywords: str, page_size: int = 40) -> list[dict]:
        """Search the catalog by keywords, normalised to the scraper's search-result dict shape."""
        data = await self.search_catalog_items(keywords, page_size=page_size)
        return [normalise_catalog_item(i, self.marketplace_id) for i in data.get("items", [])]

    async def get_rank_snapshot(self, asin: str) -> dict:
        """Look up one ASIN's current BSR, normalised to ScraperService.scrape_rank_snapshot's dict shape.

        price/stock fields come back None/True — the Catalog API carries neither, so the
        tracker only scrapes a page for those when low stock makes them worth the request.
        """
        data = await self.get_catalog_item(asin)
        n = normalise_catalog_item(data, self.marketplace_id)
        return {"asin": asin, "price": None, "current_bsr": n["bsr"], "bsr_category": n["bsr_category"],
                "current_subcategory_bsr": n["current_subcategory_bsr"], "subcategory_name": n["subcategory_name"],
                "stock_level": None, "stock_text": None, "is_in_stock": True}

    # ------------------------------------------------------------------
    # 3. Get competitive pricing
    # ------------------------------------------------------------------
    async def get_competitive_pricing(self, asin: str) -> dict:
        """Get competitive pricing data for an ASIN."""
        params = {
            "MarketplaceId": self.marketplace_id,
            "Asins": asin,
            "ItemType": "Asin",
        }
        data = await self._request(
            "GET",
            "/products/pricing/v0/competitivePrice",
            params=params,
            rate_limit_key="spapi:pricing",
        )
        return data

    # ------------------------------------------------------------------
    # 4. Get product fees estimate
    # ------------------------------------------------------------------
    async def get_fees_estimate(
        self,
        asin: str,
        price: float,
        is_fba: bool = True,
        currency: str = "USD",
    ) -> dict:
        """Get FBA/FBM fee estimate for a product at a given price."""
        body = {
            "FeesEstimateRequest": {
                "MarketplaceId": self.marketplace_id,
                "IsAmazonFulfilled": is_fba,
                "PriceToEstimateFees": {
                    "ListingPrice": {
                        "CurrencyCode": currency,
                        "Amount": price,
                    },
                },
                "Identifier": f"{asin}-fee-estimate",
            },
        }
        data = await self._request(
            "POST",
            f"/products/fees/v0/items/{asin}/feesEstimate",
            json_body=body,
            rate_limit_key="spapi:fees",
        )
        return data

    # ------------------------------------------------------------------
    # 5. Parse fees from estimate response
    # ------------------------------------------------------------------
    @staticmethod
    def parse_fees(fees_response: dict) -> dict:
        """Extract structured fee data from SP-API fees estimate response."""
        try:
            payload = fees_response.get("payload", fees_response)
            fee_detail = payload.get("FeesEstimateResult", {}).get("FeesEstimate", {})

            total_amount = fee_detail.get("TotalFeesEstimate", {}).get("Amount", 0)

            fee_breakdown = {}
            for fee_item in fee_detail.get("FeeDetailList", []):
                fee_type = fee_item.get("FeeType", "Unknown")
                fee_amount = fee_item.get("FeeAmount", {}).get("Amount", 0)
                fee_breakdown[fee_type] = float(fee_amount)

            return {
                "total_fees": float(total_amount),
                "referral_fee": fee_breakdown.get("ReferralFee", 0.0),
                "fba_fee": fee_breakdown.get("FBAFees", 0.0),
                "closing_fee": fee_breakdown.get("ClosingFee", 0.0),
                "variable_closing_fee": fee_breakdown.get("VariableClosingFee", 0.0),
                "fee_breakdown": fee_breakdown,
            }
        except Exception:
            return {
                "total_fees": 0.0,
                "referral_fee": 0.0,
                "fba_fee": 0.0,
                "closing_fee": 0.0,
                "variable_closing_fee": 0.0,
                "fee_breakdown": {},
            }

    # ------------------------------------------------------------------
    # 6. Extract sales rank from catalog item
    # ------------------------------------------------------------------
    @staticmethod
    def extract_sales_rank(catalog_item: dict) -> dict:
        """Extract BSR data from a catalog item response."""
        try:
            sales_ranks = catalog_item.get("salesRanks", [])
            if not sales_ranks:
                return {"bsr": None, "category": None, "sub_ranks": []}

            # First marketplace's ranks
            marketplace_ranks = sales_ranks[0] if sales_ranks else {}
            class_ranks = marketplace_ranks.get("classificationRanks", [])
            display_ranks = marketplace_ranks.get("displayGroupRanks", [])

            # Primary BSR is typically the display group rank
            primary_bsr = None
            primary_category = None
            sub_ranks = []

            if display_ranks:
                primary = display_ranks[0]
                primary_bsr = primary.get("rank")
                primary_category = primary.get("title")

            for cr in class_ranks:
                sub_ranks.append({
                    "rank": cr.get("rank"),
                    "category": cr.get("title"),
                })

            return {
                "bsr": primary_bsr,
                "category": primary_category,
                "sub_ranks": sub_ranks,
            }
        except Exception:
            return {"bsr": None, "category": None, "sub_ranks": []}

    # ------------------------------------------------------------------
    # 7. Extract product summary from catalog item
    # ------------------------------------------------------------------
    @staticmethod
    def extract_product_summary(catalog_item: dict) -> dict:
        """Extract key product info from catalog item summaries."""
        try:
            summaries = catalog_item.get("summaries", [])
            if not summaries:
                return {}

            summary = summaries[0]
            return {
                "title": summary.get("itemName"),
                "brand": summary.get("brand"),
                "manufacturer": summary.get("manufacturer"),
                "category": summary.get("browseClassification", {}).get("displayName"),
                "category_id": summary.get("browseClassification", {}).get("classificationId"),
                "item_classification": summary.get("itemClassification"),
                "product_type": catalog_item.get("productTypes", [{}])[0].get("productType") if catalog_item.get("productTypes") else None,
            }
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # 8. Batch: get full product data (catalog + fees)
    # ------------------------------------------------------------------
    async def get_full_product_data(
        self,
        asin: str,
        estimated_price: float | None = None,
    ) -> dict:
        """Get comprehensive product data: catalog info + fees estimate."""
        catalog_data = await self.get_catalog_item(asin)

        summary = self.extract_product_summary(catalog_data)
        sales_rank = self.extract_sales_rank(catalog_data)

        result = {
            "asin": asin,
            "catalog_data": catalog_data,
            "summary": summary,
            "sales_rank": sales_rank,
            "fees": None,
        }

        # Get fees if we have a price
        if estimated_price and estimated_price > 0:
            try:
                fees_response = await self.get_fees_estimate(asin, estimated_price)
                result["fees"] = self.parse_fees(fees_response)
            except Exception as e:
                logger.warning("Could not get fees for ASIN %s: %s", asin, e)

        return result
