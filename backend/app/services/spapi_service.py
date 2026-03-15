"""Amazon SP-API service wrapper for product data, fees, and BSR."""

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from app.core.exceptions import SPAPIError
from app.core.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

# SP-API endpoints
SP_API_BASE = "https://sellingpartnerapi-na.amazon.com"
TOKEN_URL = "https://api.amazon.com/auth/o2/token"


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
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        aws_access_key: str | None = None,
        aws_secret_key: str | None = None,
        marketplace_id: str = "ATVPDKIKX0DER",  # US marketplace
        rate_limiter: RateLimiter | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.aws_access_key = aws_access_key
        self.aws_secret_key = aws_secret_key
        self.marketplace_id = marketplace_id
        self.rate_limiter = rate_limiter

        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None
        self._http_client = httpx.AsyncClient(timeout=30.0)

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
        """Make an authenticated request to SP-API."""
        if self.rate_limiter:
            await self.rate_limiter.check_rate(rate_limit_key, max_requests=10, window_seconds=1)

        token = await self._ensure_access_token()

        headers = {
            "x-amz-access-token": token,
            "Content-Type": "application/json",
            "User-Agent": "Omniscient/1.0 (Language=Python)",
        }

        url = f"{SP_API_BASE}{path}"

        try:
            response = await self._http_client.request(
                method=method,
                url=url,
                params=params,
                json=json_body,
                headers=headers,
            )

            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", "2"))
                raise SPAPIError(
                    f"SP-API rate limit exceeded",
                    retry_after=retry_after,
                )

            response.raise_for_status()
            return response.json()

        except SPAPIError:
            raise
        except httpx.HTTPStatusError as e:
            raise SPAPIError(
                f"SP-API request failed ({e.response.status_code}): {e.response.text[:500]}"
            ) from e
        except Exception as e:
            raise SPAPIError(f"SP-API request error: {e}") from e

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
