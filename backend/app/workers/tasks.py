"""Celery task definitions for Omniscient background processing."""

import asyncio
import logging
import re
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import TYPE_CHECKING

from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.exceptions import ScrapingError, WrongMarketplaceError
from app.workers.celery_app import celery_app

# Only imported for type hints — the real imports stay local to the
# functions that use them (this file's existing lazy-import convention).
if TYPE_CHECKING:
    from app.scraping.page_cache import PageCache
    from app.scraping.pacing import SharedPacer
    from app.scraping.session import BrowserSession
    from app.services.bsr_tracker import BSRTracker
    from app.services.sales_velocity_service import SalesVelocityService
    from app.services.scraper_service import ScraperService
    from app.services.spapi_service import SPAPIService

logger = logging.getLogger(__name__)

# The niches.last_error column is TEXT but we still cap what we store —
# scraper/LLM exceptions can carry huge stack traces that would bloat the row.
MAX_STORED_ERROR_CHARS = 2000

# Per-task time limit overrides (seconds). These are tighter than the global
# default in celery_app.py because a hung Playwright page load or scrape loop
# should not be allowed to occupy a worker slot as long as a full analysis run.
TRACKING_SOFT_LIMIT_SECONDS = 20 * 60
TRACKING_HARD_LIMIT_SECONDS = 25 * 60
COMPETITOR_REFRESH_SOFT_LIMIT_SECONDS = 10 * 60
COMPETITOR_REFRESH_HARD_LIMIT_SECONDS = 12 * 60

# Each tracked product costs one page load per 6h beat run, so we cap how
# much work a single niche can generate and stop tracking niches nobody has
# rescored recently — a niche the user has moved on from doesn't need a
# live BSR chart anymore.
TRACKED_PRODUCTS_PER_NICHE = 20
TRACKING_WINDOW_DAYS = 30

# A product this low on stock can sell out (and its price/BSR swing) before the next
# 6h tracker run, so it earns a real page scrape even when SP-API is the BSR source.
LOW_STOCK_THRESHOLD = 20

# A thinner SP-API catalog search result is less complete than the SERP itself, so we
# only trust it standalone at or above this size.
MIN_SPAPI_SEARCH_RESULTS = 10
SERP_FALLBACK_PAGES = 3
SERP_ENRICHMENT_PAGES = 1

# Each detail page is one live page load, so only the top of the SERP gets one.
MAX_DETAILED_PRODUCTS = 20

# Short enough that a hung Redis fails fast and the shared pacer falls back to
# pacing locally, instead of stalling a worker slot for the rest of the run.
REDIS_SOCKET_TIMEOUT_SECONDS = 2.0

# The only page verdict that means "this is the real product page".
REAL_PAGE_VERDICT = "ok"

# How many weeks SalesForecastService projects. Also the scorer's
# "never breaks even" value for break_even_week_base.
FORECAST_HORIZON_WEEKS = 52


@dataclass(frozen=True)
class TrackingContext:
    """Bundles the collaborators one niche's product-tracking pass shares, so per-product calls take a single object instead of three positional args."""

    scraper: "ScraperService"
    tracker: "BSRTracker"
    velocity_svc: "SalesVelocityService"
    # None when SP-API isn't configured for this niche's marketplace — BSR then always
    # comes from scrape_rank_snapshot instead.
    spapi: "SPAPIService | None" = None


# ---------------------------------------------------------------------------
# Worker runtime — one event loop and one async engine per worker *process*.
# WHY: asyncpg pools are bound to the loop that created them. Creating a new
# loop per task forced a new engine per task, which leaked connections.
# Keeping a single loop alive for the process lifetime lets us keep one engine.
# ---------------------------------------------------------------------------
_loop: asyncio.AbstractEventLoop | None = None
_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None

WORKER_POOL_SIZE = 5
WORKER_POOL_OVERFLOW = 5


def _get_loop() -> asyncio.AbstractEventLoop:
    """Return the process-wide event loop, creating it on first use."""
    global _loop
    if _loop is None or _loop.is_closed():
        _loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_loop)
    return _loop


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory, creating the engine on first use."""
    global _engine, _session_factory
    if _session_factory is None:
        _get_loop()
        _engine = create_async_engine(
            Settings().DATABASE_URL, echo=False,
            pool_size=WORKER_POOL_SIZE, max_overflow=WORKER_POOL_OVERFLOW, pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(bind=_engine, class_=AsyncSession, expire_on_commit=False)
    return _session_factory


def _run_async(coro):
    """Run a coroutine on the process-wide loop. Cancels it if the run is interrupted."""
    loop = _get_loop()
    task = loop.create_task(coro)
    try:
        return loop.run_until_complete(task)
    except BaseException:
        # WHY: Celery's SoftTimeLimitExceeded is raised from a signal handler and escapes
        # run_until_complete while the coroutine is still pending. Left alone it would resume
        # on the next task that touches this loop.
        task.cancel()
        loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
        raise


def _dispose_runtime() -> None:
    """Close the engine and loop. Called on worker shutdown."""
    global _engine, _session_factory, _loop
    try:
        if _engine is not None and _loop is not None and not _loop.is_closed():
            _loop.run_until_complete(_engine.dispose())
    finally:
        if _loop is not None and not _loop.is_closed():
            _loop.close()
        _engine = _session_factory = _loop = None


def _reset_runtime_for_tests() -> None:
    """Dispose the cached runtime so the next call rebuilds it from scratch."""
    _dispose_runtime()


def _get_llm_client():
    """Create an LLM client from settings. Returns None if no API key is configured."""
    from app.llm.factory import create_llm_client
    try:
        return create_llm_client(Settings())
    except Exception as e:
        logger.warning("LLM client not available (LLM-powered steps will be skipped): %s", e)
        return None


def _build_browser_session(marketplace: str, pacer: "SharedPacer | None" = None) -> "BrowserSession":
    """Return an unopened BrowserSession for this marketplace, behind the proxy configured in settings."""
    from app.core.marketplace import get_marketplace
    from app.scraping.session import BrowserSession
    from app.services.scraper_service import build_proxy_manager_from_settings

    return BrowserSession(get_marketplace(marketplace), build_proxy_manager_from_settings(), pacer=pacer)


@asynccontextmanager
async def _redis_for_run():
    """Yield one Redis client for this run; the page cache and the shared pacer both use it."""
    from redis.asyncio import Redis

    redis = Redis.from_url(
        Settings().REDIS_URL,
        decode_responses=True,
        socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
        socket_connect_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
    )
    try:
        yield redis
    finally:
        await redis.aclose()


def _page_cache_for(redis, force: bool) -> "PageCache | None":
    """WHY None on force: a forced re-run exists to get fresh data, not last run's cached pages."""
    if force:
        return None
    from app.scraping.page_cache import PageCache
    return PageCache(redis)


def _shared_pacer(redis, site: str) -> "SharedPacer":
    """Pacer for `site` ('amazon' or '1688') shared across worker processes through Redis."""
    from app.scraping.pacing import ALIBABA_GAP_SECONDS, AMAZON_GAP_SECONDS, SharedPacer, pacer_for

    gaps = {"amazon": AMAZON_GAP_SECONDS, "1688": ALIBABA_GAP_SECONDS}
    if site not in gaps:
        raise ValueError(f"Unknown pacing site {site!r}; expected one of {sorted(gaps)}")
    return SharedPacer(redis, *gaps[site], fallback=pacer_for(site))


# ═══════════════════════════════════════════════════════════════════════════
# 1. Full Niche Analysis Pipeline
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(bind=True, name="app.workers.tasks.run_full_analysis", max_retries=2)
def run_full_analysis(self, niche_id: int, keyword: str, marketplace: str = "US", options: dict | None = None, product_asins: list[str] | None = None):
    """
    Master analysis pipeline for a niche.

    Steps:
    1. Scrape Amazon search results for the keyword (skipped if product_asins provided)
    2. Scrape top product pages (details, BSR, reviews)
    3. Run competitor analysis
    4. Fetch supplier data
    5. Build PPC strategy
    6. Build review strategy
    7. Generate financial projections
    8. Generate marketing plan
    9. Compute Omniscient Score and save recommendation

    Parameters
    ----------
    marketplace : str
        Amazon marketplace code (e.g. "US", "AU").
    product_asins : list[str] | None
        If provided, skip scraping and filter to only these ASINs (sub-niche flow).
    """
    options = dict(options or {})
    if self.request.retries > 0:
        # WHY: a retry after a mid-pipeline failure would otherwise duplicate suppliers/recommendations.
        options["force"] = True
    logger.info("Starting full analysis for niche %d: %s (marketplace=%s)", niche_id, keyword, marketplace)

    try:
        return _run_async(_run_full_analysis_async(self, niche_id, keyword, options, product_asins=product_asins, marketplace=marketplace))
    except SoftTimeLimitExceeded:
        # A retry would just re-run the same slow pipeline and hit the same limit again,
        # so mark the niche failed instead of retrying.
        logger.error("Analysis for niche %d exceeded the soft time limit", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", "Timed out"))
        raise
    except WrongMarketplaceError as exc:
        # The redirect is decided by the exit IP's country; a retry lands in the same place.
        logger.error("Analysis for niche %d cannot run from this network: %s", niche_id, exc)
        _run_async(_update_niche_status(niche_id, "failed", str(exc)))
        raise
    except Exception as exc:
        logger.exception("Full analysis failed for niche %d", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", str(exc)))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


# ═══════════════════════════════════════════════════════════════════════════
# 1b. Discovery Phase (sub-niche detection)
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(bind=True, name="app.workers.tasks.run_discovery", max_retries=2)
def run_discovery(self, niche_id: int, keyword: str, marketplace: str = "US", options: dict | None = None):
    """
    Phase A: Scrape products, detect heterogeneity, optionally cluster sub-niches.

    Returns
    -------
    dict
        If narrow: {"is_broad": false, "niche_id": N}
        If broad:  {"is_broad": true, "sub_niches": [...], "niche_id": N, "heterogeneity": {...}}
    """
    options = options or {}
    logger.info("Starting discovery for niche %d: %s (marketplace=%s)", niche_id, keyword, marketplace)

    try:
        return _run_async(_run_discovery_async(self, niche_id, keyword, options, marketplace=marketplace))
    except SoftTimeLimitExceeded:
        # A retry would just re-run the same slow pipeline and hit the same limit again,
        # so mark the niche failed instead of retrying.
        logger.error("Discovery for niche %d exceeded the soft time limit", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", "Timed out"))
        raise
    except Exception as exc:
        logger.exception("Discovery failed for niche %d", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", str(exc)))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_discovery_async(task, niche_id: int, keyword: str, options: dict, marketplace: str = "US"):
    """Async implementation of the discovery pipeline."""
    from app.models.niche import Niche
    from app.services.scraper_service import ScraperService

    session_factory = _get_session_factory()
    llm_client = _get_llm_client()

    # WHY: one browser session for the whole run, so every page load shares the
    # same cookies and fingerprint instead of looking like a brand-new visitor.
    async with (
        session_factory() as db,
        _redis_for_run() as redis,
        _build_browser_session(marketplace, pacer=_shared_pacer(redis, "amazon")) as browser,
    ):
        page_cache = _page_cache_for(redis, options.get("force", False))
        scraper = ScraperService(
            proxy_manager=browser.proxy_manager, marketplace=marketplace, session=browser,
            page_cache=page_cache, event_sink=session_factory,
        )

        # Update status to discovering
        await db.execute(
            update(Niche).where(Niche.id == niche_id).values(status="discovering")
        )
        await db.commit()

        # ── Step 1: Scrape search results ──────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_search", "progress": 5})
        products_data = await _scrape_search_results(scraper, keyword, marketplace)

        if not products_data:
            await _update_niche_status(niche_id, "failed", "No products found for keyword")
            raise ScrapingError(f"No products found for keyword '{keyword}'")

        # ── Step 2: Save products ──────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 10})
        await _save_products(db, niche_id, products_data)

        # ── Step 3: Scrape top product details ─────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 15})
        from app.workers.pipeline_steps.product_details import scrape_product_details
        detailed_products = await scrape_product_details(db, products_data[:MAX_DETAILED_PRODUCTS], scraper, marketplace)

        # Merge detail data back
        detail_by_asin = {d["asin"]: d for d in detailed_products if d.get("asin")}
        for p in products_data:
            detail = detail_by_asin.get(p.get("asin"))
            if detail:
                if detail.get("price") is not None:
                    p["price"] = detail["price"]
                if detail.get("rating") is not None:
                    p["rating"] = detail["rating"]
                if detail.get("review_count") is not None:
                    p["review_count"] = detail["review_count"]

        # ── Step 4: Detect heterogeneity ───────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "detecting_sub_niches", "progress": 25})
        from app.services.sub_niche_service import SubNicheService
        sub_niche_svc = SubNicheService(llm_client)

        heterogeneity = sub_niche_svc.detect_heterogeneity(products_data)
        logger.info(
            "Heterogeneity for '%s': is_broad=%s, price_cv=%.3f, title_diversity=%.3f",
            keyword, heterogeneity["is_broad"], heterogeneity["price_cv"],
            heterogeneity["title_diversity"],
        )

        if not heterogeneity["is_broad"]:
            # Narrow keyword — update status and return
            await db.execute(
                update(Niche).where(Niche.id == niche_id).values(
                    status="discovered",
                    sub_niche_metadata={"is_broad": False, "heterogeneity": heterogeneity},
                )
            )
            await db.commit()
            task.update_state(state="PROGRESS", meta={"step": "complete", "progress": 100})
            return {"is_broad": False, "niche_id": niche_id}

        # ── Step 5: Cluster sub-niches via LLM ────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "clustering", "progress": 30})
        sub_niches = await sub_niche_svc.cluster_sub_niches(keyword, products_data)

        # Save metadata to niche
        await db.execute(
            update(Niche).where(Niche.id == niche_id).values(
                status="discovered",
                sub_niche_metadata={
                    "is_broad": True,
                    "heterogeneity": heterogeneity,
                    "sub_niches": sub_niches,
                },
            )
        )
        await db.commit()

        task.update_state(state="PROGRESS", meta={"step": "complete", "progress": 100})
        return {
            "is_broad": True,
            "sub_niches": sub_niches,
            "niche_id": niche_id,
            "heterogeneity": heterogeneity,
        }


# ═══════════════════════════════════════════════════════════════════════════
# 1c. Niche discovery — expand a seed into ranked candidate niches to analyse
# ═══════════════════════════════════════════════════════════════════════════


@celery_app.task(
    bind=True, name="app.workers.tasks.discover_opportunities", max_retries=1,
    soft_time_limit=TRACKING_SOFT_LIMIT_SECONDS, time_limit=TRACKING_HARD_LIMIT_SECONDS,
)
def discover_opportunities(self, seed: str, marketplace: str = "AU"):
    """Expand a seed keyword into ranked candidate niches. Returns {seed, marketplace, candidates}."""
    logger.info("Discovering opportunities for seed '%s' (marketplace=%s)", seed, marketplace)
    try:
        return _run_async(_discover_opportunities_async(seed, marketplace))
    except SoftTimeLimitExceeded:
        logger.error("Discovery for '%s' exceeded the soft time limit", seed)
        raise


async def _discover_opportunities_async(seed: str, marketplace: str) -> dict:
    """Open one browser session and rank candidate niches for the seed."""
    from app.services.discovery import DiscoveryService
    from app.services.scraper_service import ScraperService

    session_factory = _get_session_factory()
    async with (
        _redis_for_run() as redis,
        _build_browser_session(marketplace, pacer=_shared_pacer(redis, "amazon")) as browser,
    ):
        scraper = ScraperService(
            proxy_manager=browser.proxy_manager, marketplace=marketplace, session=browser,
            page_cache=_page_cache_for(redis, force=False), event_sink=session_factory,
        )
        candidates = await DiscoveryService(scraper).discover(seed)
    return {"seed": seed, "marketplace": marketplace, "candidates": candidates}


async def _run_full_analysis_async(task, niche_id: int, keyword: str, options: dict, product_asins: list[str] | None = None, marketplace: str = "US"):
    """Async implementation of the full analysis pipeline."""
    from app.models.niche import Niche
    from app.models.product import Product
    from app.services.scraper_service import ScraperService

    session_factory = _get_session_factory()
    llm_client = _get_llm_client()

    # WHY: one browser session for the whole run (search, product pages, keyword
    # SERPs), so every page load shares the same cookies and fingerprint. It is
    # opened even for the sub-niche flow because keyword research still scrapes.
    async with (
        session_factory() as db,
        _redis_for_run() as redis,
        _build_browser_session(marketplace, pacer=_shared_pacer(redis, "amazon")) as browser,
    ):
        page_cache = _page_cache_for(redis, options.get("force", False))
        scraper = ScraperService(
            proxy_manager=browser.proxy_manager, marketplace=marketplace, session=browser,
            page_cache=page_cache, event_sink=session_factory,
        )

        # Update status to analyzing
        await db.execute(
            update(Niche).where(Niche.id == niche_id).values(status="analyzing")
        )
        await db.commit()

        if options.get("force"):
            from app.workers.pipeline_steps.reset import reset_niche_analysis_data
            await reset_niche_analysis_data(db, niche_id)
            await db.commit()

        if product_asins:
            # ── Sub-niche flow: load products from parent niche by ASIN ──
            task.update_state(state="PROGRESS", meta={"step": "loading_products", "progress": 5})

            # Look up the parent niche to get its products
            niche_row = (await db.execute(select(Niche).where(Niche.id == niche_id))).scalar_one_or_none()
            parent_id = niche_row.parent_niche_id if niche_row else None

            # Load products that match the given ASINs. WHY in_([parent, child]): the first
            # run moves these products from the parent niche to this child, so a re-run (retry,
            # double-click, forced re-analyse) must also find the ones already reassigned —
            # filtering on the parent alone would match zero rows the second time.
            allowed_niche_ids = [nid for nid in (parent_id, niche_id) if nid is not None]
            product_query = select(Product).where(Product.asin.in_(product_asins))
            if allowed_niche_ids:
                product_query = product_query.where(Product.niche_id.in_(allowed_niche_ids))
            result = await db.execute(product_query)
            db_products = result.scalars().all()

            if not db_products:
                await _update_niche_status(niche_id, "failed", "No products found for this sub-niche")
                raise ScrapingError(f"No products found for sub-niche {niche_id} (ASINs: {product_asins})")

            # Reassign products to child niche
            for p in db_products:
                p.niche_id = niche_id
            await db.flush()
            await db.commit()

            products_data = [_stored_product_as_detail(p) for p in db_products]
            detailed_products = products_data  # Already have detail data
            task.update_state(state="PROGRESS", meta={"step": "products_scraped", "progress": 30})

        else:
            # ── Standard flow: scrape from scratch ────────────────────────

            # ── Step 1: Scrape search results ──────────────────────────────
            task.update_state(state="PROGRESS", meta={"step": "scraping_search", "progress": 5})
            products_data = await _scrape_search_results(scraper, keyword, marketplace)

            if not products_data:
                await _update_niche_status(niche_id, "failed", "No products found for keyword")
                raise ScrapingError(f"No products found for keyword '{keyword}'")

            # ── Step 2: Save products and scrape details ───────────────────
            task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 15})
            product_ids = await _save_products(db, niche_id, products_data)

            # Scrape individual product pages for detailed data
            from app.workers.pipeline_steps.product_details import scrape_product_details
            detailed_products = await scrape_product_details(db, products_data[:MAX_DETAILED_PRODUCTS], scraper, marketplace)

            # Merge detail page data back into products_data so downstream
            # services (competitor analysis, scoring, financials) use the
            # enriched values (price, rating, review_count, BSR, etc.)
            detail_by_asin = {d["asin"]: d for d in detailed_products if d.get("asin")}
            for p in products_data:
                detail = detail_by_asin.get(p.get("asin"))
                if detail:
                    if detail.get("price") is not None:
                        p["price"] = detail["price"]
                    if detail.get("rating") is not None:
                        p["rating"] = detail["rating"]
                    if detail.get("review_count") is not None:
                        p["review_count"] = detail["review_count"]
                    if detail.get("current_bsr") is not None:
                        p["bsr"] = detail["current_bsr"]
                    if detail.get("brand"):
                        p["brand"] = detail["brand"]
                    for key in ("bullet_count", "image_count", "has_video",
                                "has_a_plus", "has_brand_story", "seller_id", "sold_by_amazon",
                                "dimensions", "weight", "date_first_available",
                                "star_distribution", "variation_count",
                                "category_path", "list_price", "seller_count",
                                "fbt_asins", "qa_count", "deal_badge",
                                "amazons_choice_keyword", "review_attributes",
                                "comparison_asins"):
                        if detail.get(key) is not None:
                            p[key] = detail[key]

            # Ensure search result data flows into detailed_products
            search_data = {
                p.get("asin"): p for p in products_data if p.get("asin")
            }
            for d in detailed_products:
                search = search_data.get(d.get("asin"), {})
                if not d.get("image_url") and search.get("image_url"):
                    d["image_url"] = search["image_url"]
                if not d.get("title") and search.get("title"):
                    d["title"] = search["title"]
                if d.get("review_count") is None and search.get("review_count") is not None:
                    d["review_count"] = search["review_count"]
                if d.get("price") is None and search.get("price") is not None:
                    d["price"] = search["price"]
                if d.get("rating") is None and search.get("rating") is not None:
                    d["rating"] = search["rating"]
                if d.get("bsr") is None and d.get("current_bsr") is None and search.get("bsr") is not None:
                    d["bsr"] = search["bsr"]

            task.update_state(state="PROGRESS", meta={"step": "products_scraped", "progress": 30})

        # ── Step 2b: Keyword research (autocomplete + SERP) ────────
        task.update_state(state="PROGRESS", meta={"step": "keyword_research", "progress": 31})
        keyword_research_summary = None
        try:
            from app.services.keyword_research import KeywordResearchService
            kw_research_svc = KeywordResearchService(db, scraper=scraper, marketplace=marketplace)
            keyword_research_summary = await kw_research_svc.research_keywords(
                niche_id=niche_id,
                seed_keyword=keyword,
            )
            await db.flush()
            logger.info(
                "Keyword research complete: %d keywords discovered",
                keyword_research_summary.get("total_keywords_discovered", 0),
            )
        except Exception as e:
            logger.warning("Keyword research failed: %s", e)

        # ── Step 2c: Extract reviews from product page data ─────────
        # Reviews are embedded in product detail pages (top reviews section),
        # extracted during scrape_product_page(). No separate page loads needed.
        task.update_state(state="PROGRESS", meta={"step": "review_extraction", "progress": 32})
        from app.workers.pipeline_steps.reviews import save_reviews_for_product
        reviews_scraped = 0
        for detail in detailed_products[:10]:
            asin = detail.get("asin")
            page_reviews = detail.get("page_reviews", [])
            if not page_reviews or not asin:
                continue

            # Find product in DB
            p_stmt = select(Product).where(Product.asin == asin)
            product_obj = (await db.execute(p_stmt)).scalar_one_or_none()
            if not product_obj:
                continue

            reviews_scraped += await save_reviews_for_product(db, product_obj, page_reviews)

        logger.info("Extracted %d reviews from product pages", reviews_scraped)

        # ── Step 3: Competitor analysis ────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "competitor_analysis", "progress": 35})
        from app.services.competitor_service import CompetitorService
        competitor_svc = CompetitorService(db, llm_client)

        competitor_landscape = await competitor_svc.analyze_landscape(
            niche_id=niche_id,
            products=products_data[:MAX_DETAILED_PRODUCTS],
            category=keyword,
        )
        if competitor_landscape:
            competitor_landscape["marketplace"] = marketplace
            try:
                saved_competitors = await competitor_svc.persist_landscape(niche_id, competitor_landscape)
                await db.flush()
                logger.info("Persisted %d competitor rows for niche %d", saved_competitors, niche_id)
            except Exception as e:
                logger.warning("Persisting competitors failed: %s", e)

        # ── Step 4: Collect reviews + sentiment/pain-point analysis ─────
        task.update_state(state="PROGRESS", meta={"step": "review_analysis", "progress": 38})
        from app.services.review_analyzer import ReviewAnalyzer
        from app.workers.pipeline_steps.reviews import collect_reviews_by_asin, flatten_reviews, run_review_analysis

        competitor_reviews_map = await collect_reviews_by_asin(db, niche_id)
        review_insights = await run_review_analysis(llm_client, competitor_reviews_map, keyword)

        # ── Step 4b: Review Intelligence (deep cross-product synthesis) ──
        task.update_state(state="PROGRESS", meta={"step": "review_intelligence", "progress": 42})
        review_intelligence = None
        product_titles_map = {
            p.get("asin", ""): p.get("title", "")
            for p in detailed_products if p.get("asin")
        }
        if competitor_reviews_map and llm_client:
            try:
                review_intelligence = await ReviewAnalyzer(llm_client).generate_review_intelligence(
                    all_reviews=flatten_reviews(competitor_reviews_map),
                    product_reviews=competitor_reviews_map,
                    niche_keyword=keyword,
                    product_titles=product_titles_map,
                )
            except Exception as e:
                logger.warning("Review intelligence failed: %s", e)

        # ── Step 4c: Niche Intelligence Report (LLM) ──────────────────
        task.update_state(state="PROGRESS", meta={"step": "niche_intelligence", "progress": 45})
        from app.services.niche_intelligence import NicheIntelligenceService

        niche_intelligence = None
        product_overviews = None
        if llm_client:
            try:
                intel_svc = NicheIntelligenceService(llm_client)
                niche_intelligence = await intel_svc.generate_niche_overview(
                    keyword, detailed_products, competitor_landscape,
                    _build_base_metrics(competitor_landscape, detailed_products, marketplace=marketplace),
                )
            except Exception as e:
                logger.warning("Niche intelligence generation failed: %s", e)

            try:
                intel_svc = NicheIntelligenceService(llm_client)
                competitor_details = (
                    competitor_landscape.get("competitor_details", [])
                    if competitor_landscape else []
                )
                product_overviews = await intel_svc.generate_product_overviews(
                    detailed_products, competitor_details,
                )
            except Exception as e:
                logger.warning("Product overviews generation failed: %s", e)

        # ── Step 4d: Product Blueprint (complaint analysis) ──────────
        task.update_state(state="PROGRESS", meta={"step": "product_blueprint", "progress": 48})
        from app.services.product_blueprint import ProductBlueprintService
        blueprint_svc = ProductBlueprintService(llm_client)

        product_blueprint = None
        # competitor_reviews_map already collected in step 4 above
        competitor_meta = _build_competitor_metadata(detailed_products)
        # NOTE: the AI blueprint and the consolidated financial report are paid features.
        # The worker reads the same LICENSE_KEY as the API, so an unlicensed deployment
        # skips both steps entirely. Read the license once for both checks.
        from app.licensing import FEATURE_BLUEPRINT, FEATURE_FINANCIAL_REPORT, current_license

        licensed_features = current_license().features
        if competitor_reviews_map and llm_client and FEATURE_BLUEPRINT in licensed_features:
            try:
                product_blueprint = await blueprint_svc.generate_blueprint(
                    niche_keyword=keyword,
                    competitor_reviews=competitor_reviews_map,
                    competitor_metadata=competitor_meta,
                    price_range=competitor_landscape.get("price_stats") if competitor_landscape else None,
                )
            except Exception as e:
                logger.warning("Product blueprint generation failed: %s", e)

        # ── Step 5: Generate product spec ──────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "product_spec", "progress": 52})
        from app.services.spec_generator import SpecGenerator
        spec_gen = SpecGenerator(llm_client)

        # Extract common data used by both product spec and product ideas
        pain_points = review_insights.get("pain_points", []) if review_insights else []
        positive_themes = review_insights.get("positive_themes", []) if review_insights else []
        price_range = competitor_landscape.get("price_stats", {}) if competitor_landscape else {}
        competitor_list = competitor_landscape.get("competitors", []) if competitor_landscape else []

        product_spec = None
        if llm_client:
            try:
                product_spec = await spec_gen.generate_product_spec(
                    niche_keyword=keyword,
                    pain_points=pain_points,
                    positive_themes=positive_themes,
                    competitor_data=competitor_list,
                    price_range=price_range,
                )
            except Exception as e:
                logger.warning("Product spec generation failed: %s", e)

        # ── Step 5b: Product Ideas ──────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "product_ideas", "progress": 53})
        product_ideas = None
        if llm_client:
            try:
                product_ideas = await spec_gen.generate_product_ideas(
                    niche_keyword=keyword,
                    pain_points=pain_points,
                    positive_themes=positive_themes,
                    competitor_data=competitor_list,
                    price_range=price_range,
                    product_blueprint=product_blueprint,
                )
            except Exception as e:
                logger.warning("Product ideas generation failed: %s", e)

        # ── Step 6a: Supplier scraping from 1688 ──────────────────────
        task.update_state(state="PROGRESS", meta={"step": "supplier_scraping", "progress": 55})
        from app.core.cookie_manager import CookieManager
        from app.services.supplier_scraper import SupplierScraper

        cookie_manager = CookieManager()

        # Attempt 1688 login if credentials are configured
        settings = Settings()
        if settings.ALIBABA_1688_EMAIL and settings.ALIBABA_1688_PASSWORD:
            from app.services.alibaba_login import AlibabaLoginService
            login_svc = AlibabaLoginService(cookie_manager)
            try:
                await login_svc.ensure_logged_in(
                    settings.ALIBABA_1688_EMAIL,
                    settings.ALIBABA_1688_PASSWORD,
                )
            except Exception as e:
                logger.warning("1688 login failed: %s", e)

        supplier_scraper = SupplierScraper(cookie_manager=cookie_manager, pacer=_shared_pacer(redis, "1688"))

        scraped_suppliers: list[dict] = []
        try:
            scraped_suppliers = await supplier_scraper.search_suppliers(keyword, max_results=10)
        except Exception as e:
            logger.warning("Supplier scraping failed: %s", e)

        # Save scraped suppliers to DB
        if scraped_suppliers:
            await _save_suppliers(db, niche_id, scraped_suppliers)

        from app.services.market_signals import summarize_suppliers
        supplier_summary = summarize_suppliers(scraped_suppliers, cny_to_usd_rate=_CNY_TO_USD_RATE)

        # ── Step 6a-ii: Translate Chinese supplier fields ─────────────
        if scraped_suppliers and llm_client:
            task.update_state(state="PROGRESS", meta={"step": "translating_suppliers", "progress": 57})
            try:
                scraped_suppliers = await _translate_supplier_fields(llm_client, scraped_suppliers)
            except Exception as e:
                logger.warning("Supplier translation failed: %s", e)

        # ── Step 6a-iii: Per-product supplier matching ────────────────
        task.update_state(state="PROGRESS", meta={"step": "supplier_matching", "progress": 58})
        from app.services.supplier_match_service import SupplierMatchService

        product_supplier_matches = []
        if llm_client:
            try:
                match_svc = SupplierMatchService(
                    llm_client=llm_client,
                    supplier_scraper=supplier_scraper,
                )
                product_supplier_matches = await match_svc.find_matches_for_products(
                    products=detailed_products[:10],
                    max_suppliers_per_product=3,
                )
            except Exception as e:
                logger.warning("Per-product supplier matching failed: %s", e)

        # ── Step 6b: Supplier cost analysis ───────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "supplier_analysis", "progress": 58})

        from app.services.market_signals import apply_supplier_summary

        metrics = _build_base_metrics(
            competitor_landscape, detailed_products, keyword_research_summary, marketplace=marketplace,
        )

        from app.workers.pipeline_steps.review_velocity import apply_review_velocity
        await apply_review_velocity(
            db, niche_id, metrics, marketplace=marketplace, filter_enabled=Settings().REVIEW_VELOCITY_FILTER_ENABLED,
        )

        apply_supplier_summary(metrics, supplier_summary)
        product_dims = _extract_avg_dimensions(detailed_products)
        supplier_data = None
        try:
            supplier_data = await _analyze_suppliers(
                db, niche_id, metrics, marketplace=marketplace,
                fob_unit_cost=supplier_summary["median_fob_usd"], weight_kg=product_dims["weight_lb"] * LB_TO_KG,
            )
        except Exception as e:
            logger.warning("Supplier analysis failed: %s", e)

        # ── Step 7: Scoring (moved up to inform financial report) ──────
        task.update_state(state="PROGRESS", meta={"step": "scoring", "progress": 60})
        from app.services.scoring_service import ScoringService
        scorer = ScoringService()

        # Enrich metrics with everything we've gathered so far
        _enrich_metrics(metrics, competitor_landscape, None, None, supplier_data)

        score_result = scorer.compute_score(metrics)
        hard_filter_results = score_result.get("hard_filters", [])
        confidence_tier = score_result.get("confidence_tier")

        logger.info(
            "Scoring complete for niche %d: score=%s tier=%s",
            niche_id, score_result["omniscient_score"], confidence_tier,
        )

        # ── Step 8: PPC strategy ───────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "ppc_strategy", "progress": 65})
        from app.services.ppc_service import PPCService
        from app.workers.pipeline_steps.ppc import build_ppc_strategy, ppc_metrics_from_strategy

        ppc_strategy = None
        try:
            ppc_strategy = await build_ppc_strategy(
                PPCService(db, llm_client),
                niche_id=niche_id, keyword=keyword, metrics=metrics, competitor_landscape=competitor_landscape,
            )
            # Feed the deterministic budget numbers forward so steps 9/10/12 (review
            # strategy, forecast, financial report) see real avg_cpc/budget values
            # instead of the hard-coded defaults sprinkled through those steps.
            metrics.update(ppc_metrics_from_strategy(ppc_strategy))
            await db.flush()
        except Exception as e:
            logger.warning("PPC strategy generation failed: %s", e)

        # ── Step 9: Review strategy ────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "review_strategy", "progress": 72})
        from app.services.review_strategy import ReviewStrategyService
        review_svc = ReviewStrategyService(llm_client)

        review_strategy = None
        try:
            # Gather competitor review counts from products data
            competitor_reviews = [p.get("review_count", 0) for p in products_data[:MAX_DETAILED_PRODUCTS] if p.get("review_count")]
            review_strategy = await review_svc.generate_review_strategy(
                niche_keyword=keyword,
                competitor_reviews=competitor_reviews,
                monthly_sales_estimate=metrics.get("estimated_monthly_sales") or 100,
                product_cost=metrics.get("landed_cost") or 8,
                selling_price=metrics.get("avg_price") or 30,
            )
        except Exception as e:
            logger.warning("Review strategy generation failed: %s", e)

        # ── Step 10: Financial projections ──────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "financial_projections", "progress": 80})
        from app.services.sales_forecast import SalesForecastService
        forecast_svc = SalesForecastService(db)

        financial_summary = None
        try:
            forecast = forecast_svc.generate_forecast(
                selling_price=metrics.get("avg_price") or 30,
                landed_cost=metrics.get("landed_cost") or 8,
                fba_fees=metrics.get("fba_fees") or 5,
                base_weekly_sales=max(1, (metrics.get("estimated_monthly_sales") or 100) // 4),
                initial_ppc_daily=metrics.get("ppc_daily_budget") or 30,
            )
            financial_summary = forecast_svc.summarize_forecast(forecast)
            await forecast_svc.save_projections(niche_id, forecast)
            metrics["break_even_week_base"] = _base_case_break_even_week(financial_summary)
            from app.workers.pipeline_steps.assumptions import GAP_BREAK_EVEN, clear_data_gap
            clear_data_gap(metrics, GAP_BREAK_EVEN)

            # Calculate launch capital
            launch_capital = forecast_svc.calculate_launch_capital(
                landed_cost=metrics.get("landed_cost") or 8,
                initial_order_qty=metrics.get("initial_order_qty") or 500,
                vine_cost=review_strategy.get("vine_plan", {}).get("costs", {}).get("total_vine_cost", 0) if review_strategy else 0,
                ppc_budget_90_days=metrics.get("ppc_budget_90d") or 2700,
            )
            metrics["total_launch_capital"] = launch_capital["total_launch_capital"]

            # generate_launch_playbook (step 11) reads exactly these two keys off financial_summary.
            financial_summary["marketplace"] = marketplace
            financial_summary["total_launch_capital"] = launch_capital["total_launch_capital"]
        except Exception as e:
            logger.warning("Financial projections failed: %s", e)

        # ── Step 11: Marketing plan ────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "marketing_plan", "progress": 87})
        from app.services.marketing_service import MarketingService
        marketing_svc = MarketingService(llm_client)

        marketing_plan = None
        if product_spec and ppc_strategy and review_strategy and financial_summary:
            try:
                marketing_plan = await marketing_svc.generate_full_marketing_plan(
                    niche_keyword=keyword,
                    product_spec=product_spec,
                    ppc_strategy=ppc_strategy,
                    review_strategy=review_strategy,
                    financial_summary=financial_summary,
                )
            except Exception as e:
                logger.warning("Marketing plan generation failed: %s", e)

        # ── Step 12: Consolidated financial report ─────────────────
        task.update_state(state="PROGRESS", meta={"step": "financial_report", "progress": 90})
        from app.services.financial_report import FinancialReportService
        fin_report_svc = FinancialReportService(marketplace=marketplace)

        # The consolidated financial report is a paid feature; skip it on an unlicensed deployment.
        financial_report = None
        if FEATURE_FINANCIAL_REPORT not in licensed_features:
            logger.info("Consolidated financial report skipped: not in the installed license")
        else:
            try:
                from app.core.category_mapping import category_slugs
                duty_slug, fee_slug = category_slugs(metrics.get("category"))
                financial_report = await fin_report_svc.generate_full_report(
                    selling_price=metrics.get("avg_price") or 30,
                    # Use the real scraped 1688 FOB price when we have one; otherwise fall back
                    # to a rough share of landed cost (FOB is typically ~55% of total landed cost).
                    unit_cost_fob=metrics.get("fob_unit_cost") or (metrics.get("landed_cost") or DEFAULT_LANDED_COST_USD) * FOB_SHARE_OF_LANDED_FALLBACK,
                    product_dims=product_dims,
                    category=duty_slug,
                    fee_category=fee_slug,
                    weight_kg_per_unit=product_dims["weight_lb"] * LB_TO_KG,
                    order_quantity=metrics.get("initial_order_qty") or 500,
                    estimated_monthly_sales=metrics.get("estimated_monthly_sales") or 200,
                    avg_cpc=metrics.get("avg_cpc") or 1.50,
                    launch_ppc_daily=metrics.get("ppc_daily_budget") or 30,
                    hard_filter_results=hard_filter_results,
                    confidence_tier=confidence_tier,
                )
            except Exception as e:
                logger.warning("Consolidated financial report failed: %s", e)

        # ── Step 13: Save recommendation ───────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "saving_recommendation", "progress": 93})
        from app.services.recommendation_engine import RecommendationEngine
        engine = RecommendationEngine(db, llm_client)

        # Re-enrich metrics with PPC and review data now available
        _enrich_metrics(metrics, competitor_landscape, ppc_strategy, review_strategy, supplier_data)

        recommendation = await engine.generate_recommendation(
            niche_id=niche_id,
            metrics=metrics,
            product_spec=product_spec,
            ppc_strategy=ppc_strategy,
            review_strategy=review_strategy,
            financial_summary=financial_summary,
            marketing_plan=marketing_plan,
            product_blueprint=product_blueprint,
            financial_report=financial_report,
            niche_overview=niche_intelligence,
            product_overviews=product_overviews,
            product_ideas=product_ideas,
            review_intelligence=review_intelligence,
            product_supplier_matches=product_supplier_matches,
            competitor_landscape=competitor_landscape,
        )

        await db.commit()

        task.update_state(state="PROGRESS", meta={"step": "complete", "progress": 100})
        logger.info(
            "Full analysis complete for niche %d: score=%s tier=%s",
            niche_id,
            recommendation.get("omniscient_score"),
            recommendation.get("confidence_tier"),
        )

        return {
            "niche_id": niche_id,
            "recommendation_id": recommendation.get("recommendation_id"),
            "omniscient_score": recommendation.get("omniscient_score"),
            "confidence_tier": recommendation.get("confidence_tier"),
        }


# ═══════════════════════════════════════════════════════════════════════════
# 2. BSR & Price Tracking (periodic)
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(name="app.workers.tasks.track_bsr_prices_all")
def track_bsr_prices_all():
    """Track BSR and prices for all active niches (beat schedule)."""
    logger.info("Starting periodic BSR/price tracking for all active niches")
    _run_async(_track_bsr_all_async())


async def _track_bsr_all_async():
    """Fetch recently-scored active niches and track BSR/prices for their products."""
    from app.models.niche import Niche

    session_factory = _get_session_factory()
    async with session_factory() as db:
        # Only track niches scored within the tracking window — an older
        # niche the user isn't actively evaluating doesn't justify the
        # scraping cost of a fresh BSR chart every 6 hours.
        tracking_cutoff = datetime.now(timezone.utc) - timedelta(days=TRACKING_WINDOW_DAYS)
        stmt = select(Niche.id).where(
            Niche.status == "completed",
            Niche.last_scored_at >= tracking_cutoff,
        )
        result = await db.execute(stmt)
        niche_ids = [row[0] for row in result.all()]

    # Fan out individual tracking tasks
    for niche_id in niche_ids:
        track_bsr_prices.delay(niche_id)

    logger.info("Queued BSR tracking for %d niches", len(niche_ids))


@celery_app.task(
    name="app.workers.tasks.track_bsr_prices", max_retries=1,
    soft_time_limit=TRACKING_SOFT_LIMIT_SECONDS, time_limit=TRACKING_HARD_LIMIT_SECONDS,
)
def track_bsr_prices(niche_id: int):
    """Track BSR and prices for all products in a specific niche."""
    logger.info("Tracking BSR/prices for niche %d", niche_id)
    _run_async(_track_bsr_niche_async(niche_id))


async def _track_one_product(product, context: TrackingContext) -> None:
    """Re-scrape one product's rank/price/stock and persist all three snapshots.

    WHY: when SP-API is configured, BSR comes from the Catalog API — free of scraping
    risk, but with no price or stock. The page itself is only scraped on top of that when
    the product was already low on stock, since that is the case where price/stock can
    move before the next tracker run and are worth the extra page load.
    """
    if context.spapi is not None:
        await _track_bsr_via_spapi(product, context)
        if product.last_stock_level is not None and product.last_stock_level < LOW_STOCK_THRESHOLD:
            page_snapshot = await context.scraper.scrape_rank_snapshot(product.asin)
            await _record_snapshot(product, context, page_snapshot)
        return

    snapshot = await context.scraper.scrape_rank_snapshot(product.asin)
    await _record_snapshot(product, context, snapshot)


async def _track_bsr_via_spapi(product, context: TrackingContext) -> None:
    """Record BSR from the SP-API Catalog API. Does not touch stock history — SP-API has
    no stock data, and recording a fabricated "in stock" observation would corrupt the
    real stockout signal the velocity service reads from that history.
    """
    snapshot = await context.spapi.get_rank_snapshot(product.asin)
    await context.tracker.record_product_snapshot(
        product_id=product.id, asin=product.asin,
        bsr=snapshot["current_bsr"], category_name=snapshot["bsr_category"],
        subcategory_bsr=snapshot["current_subcategory_bsr"], subcategory_name=snapshot["subcategory_name"],
        price=snapshot["price"],
    )
    if snapshot["current_bsr"]:
        product.current_bsr = snapshot["current_bsr"]


async def _record_snapshot(product, context: TrackingContext, snapshot: dict) -> None:
    """Persist one page-scraped rank/price/stock snapshot and update the product row.

    Skips pages that were not a real product page: a soft-blocked page parses
    as "no rank, no price, in stock", and recording that would fake a restock.
    """
    if snapshot.get("verdict") != REAL_PAGE_VERDICT:
        logger.debug("Not recording snapshot for %s: page verdict was %r", product.asin, snapshot.get("verdict"))
        return
    await context.tracker.record_product_snapshot(
        product_id=product.id, asin=product.asin,
        bsr=snapshot["current_bsr"], category_name=snapshot["bsr_category"],
        subcategory_bsr=snapshot["current_subcategory_bsr"], subcategory_name=snapshot["subcategory_name"],
        price=snapshot["price"], review_count=snapshot.get("review_count"),
    )
    if snapshot["current_bsr"]:
        product.current_bsr = snapshot["current_bsr"]
    if snapshot["price"]:
        product.current_price = snapshot["price"]
    await context.velocity_svc.record_stock_snapshot(
        product_id=product.id, asin=product.asin,
        stock_level=snapshot["stock_level"], stock_text=snapshot["stock_text"], is_in_stock=snapshot["is_in_stock"],
    )
    if snapshot["stock_level"] is not None:
        product.last_stock_level = snapshot["stock_level"]


async def _track_bsr_niche_async(niche_id: int):
    """Re-scrape BSR, price, and stock for the niche's top-ranked tracked products."""
    from app.models.niche import Niche as NicheModel
    from app.models.product import Product
    from app.services.bsr_tracker import BSRTracker
    from app.services.sales_velocity_service import SalesVelocityService
    from app.services.scraper_service import ScraperService
    from app.workers.pipeline_steps.product_source import product_source_for

    session_factory = _get_session_factory()
    async with session_factory() as db:
        niche_marketplace = (await db.execute(
            select(NicheModel.marketplace).where(NicheModel.id == niche_id)
        )).scalar_one_or_none() or "US"

        stmt = (
            select(Product)
            .where(Product.niche_id == niche_id)
            .order_by(Product.search_position.asc().nullslast())
            .limit(TRACKED_PRODUCTS_PER_NICHE)
        )
        products = (await db.execute(stmt)).scalars().all()

        settings = Settings()
        spapi = _build_spapi_client(settings, niche_marketplace) if product_source_for(settings) == "spapi" else None

        try:
            # WHY: one browser session per niche, shared by every product page load.
            async with (
                _redis_for_run() as redis,
                _build_browser_session(niche_marketplace, pacer=_shared_pacer(redis, "amazon")) as browser,
            ):
                context = TrackingContext(
                    scraper=ScraperService(
                        proxy_manager=browser.proxy_manager, marketplace=niche_marketplace, session=browser,
                        # WHY page_cache=None: this scraper only calls scrape_rank_snapshot(),
                        # which never reads the cache — a fresh BSR/price/stock read is the
                        # whole point of the tracker, so it must never see a stale page.
                        page_cache=None, event_sink=session_factory,
                    ),
                    tracker=BSRTracker(db),
                    velocity_svc=SalesVelocityService(db),
                    spapi=spapi,
                )
                await _track_products(db, products, context)
        finally:
            if spapi is not None:
                await spapi.close()

        logger.info("Tracked %d products in niche %d", len(products), niche_id)


def _build_spapi_client(settings: Settings, marketplace: str) -> "SPAPIService":
    """Build one SP-API client for a niche's tracking run. Caller must close it."""
    from app.services.spapi_service import SPAPIService

    return SPAPIService(
        client_id=settings.SP_API_CLIENT_ID, client_secret=settings.SP_API_CLIENT_SECRET,
        refresh_token=settings.SP_API_REFRESH_TOKEN, marketplace=marketplace,
    )


async def _track_products(db: AsyncSession, products: list, context: TrackingContext) -> None:
    """Track each product in turn. One product failing does not stop the others."""
    for product in products:
        # NOTE: read the ASIN up front. A savepoint rollback expires the product,
        # and reloading it lazily is not allowed in an async session.
        asin = product.asin
        try:
            # WHY: a savepoint per product, so one failed insert rolls back only
            # that product and leaves the session usable for the rest.
            async with db.begin_nested():
                await _track_one_product(product, context)
        except Exception as e:
            logger.warning("Failed to track product %s (rolled back to savepoint): %s", asin, e)
            continue
        # WHY: commit after each product, not once at the end — a hard
        # time-limit kill mid-loop would otherwise lose every snapshot
        # recorded so far for this niche.
        await db.commit()


# ═══════════════════════════════════════════════════════════════════════════
# 3. Review Scraping
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(
    name="app.workers.tasks.scrape_reviews", max_retries=2,
    soft_time_limit=TRACKING_SOFT_LIMIT_SECONDS, time_limit=TRACKING_HARD_LIMIT_SECONDS,
)
def scrape_reviews(niche_id: int, asin: str, max_pages: int = 5):
    """Scrape reviews for a specific product."""
    logger.info("Scraping reviews for ASIN %s (niche %d)", asin, niche_id)
    _run_async(_scrape_reviews_async(niche_id, asin, max_pages))


async def _scrape_reviews_async(niche_id: int, asin: str, max_pages: int):
    """Scrape and store reviews for a product."""
    from app.models.product import Product
    from app.workers.pipeline_steps.reviews import save_reviews_for_product

    session_factory = _get_session_factory()
    async with session_factory() as db:
        # Find the product
        stmt = select(Product).where(Product.asin == asin, Product.niche_id == niche_id)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            logger.warning("Product %s not found in niche %d", asin, niche_id)
            return

        # Scrape reviews — determine marketplace from niche
        from app.models.niche import Niche as NicheModel
        niche_row = (await db.execute(
            select(NicheModel).where(NicheModel.id == niche_id)
        )).scalar_one_or_none()
        niche_marketplace = niche_row.marketplace if niche_row else "US"

        from app.services.scraper_service import ScraperService

        try:
            async with (
                _redis_for_run() as redis,
                _build_browser_session(niche_marketplace, pacer=_shared_pacer(redis, "amazon")) as browser,
            ):
                scraper = ScraperService(
                    proxy_manager=browser.proxy_manager, marketplace=niche_marketplace, session=browser,
                    # WHY page_cache=None: scrape_reviews() never reads the cache, so
                    # there is nothing here for a PageCache to do.
                    page_cache=None, event_sink=session_factory,
                )
                reviews_data = await scraper.scrape_reviews(asin, max_pages=max_pages)
        except Exception as e:
            logger.warning("Review scraping failed for %s: %s", asin, e)
            return

        saved = await save_reviews_for_product(db, product, reviews_data)
        await db.commit()
        logger.info("Saved %d reviews for ASIN %s", saved, asin)


# ═══════════════════════════════════════════════════════════════════════════
# 4. Competitor Data Refresh
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(name="app.workers.tasks.refresh_all_competitors")
def refresh_all_competitors():
    """Refresh competitor data for all active niches (beat schedule)."""
    logger.info("Starting competitor refresh for all active niches")
    _run_async(_refresh_all_competitors_async())


async def _refresh_all_competitors_async():
    from app.models.niche import Niche

    session_factory = _get_session_factory()
    async with session_factory() as db:
        stmt = select(Niche.id, Niche.primary_keyword).where(Niche.status == "completed")
        result = await db.execute(stmt)
        niches = result.all()

    for niche_id, keyword in niches:
        refresh_competitor_data.delay(niche_id, keyword)

    logger.info("Queued competitor refresh for %d niches", len(niches))


@celery_app.task(
    name="app.workers.tasks.refresh_competitor_data", max_retries=1,
    soft_time_limit=COMPETITOR_REFRESH_SOFT_LIMIT_SECONDS, time_limit=COMPETITOR_REFRESH_HARD_LIMIT_SECONDS,
)
def refresh_competitor_data(niche_id: int, keyword: str):
    """Refresh competitor analysis for a single niche."""
    logger.info("Refreshing competitors for niche %d", niche_id)
    _run_async(_refresh_competitor_async(niche_id, keyword))


async def _refresh_competitor_async(niche_id: int, keyword: str):
    from app.services.competitor_service import CompetitorService

    session_factory = _get_session_factory()
    llm_client = _get_llm_client()

    async with session_factory() as db:
        svc = CompetitorService(db, llm_client)
        try:
            # Fetch products from DB for this niche
            from app.models.product import Product as ProductModel
            stmt = select(ProductModel).where(ProductModel.niche_id == niche_id).limit(20)
            result = await db.execute(stmt)
            db_products = result.scalars().all()
            products_for_analysis = [
                {
                    "asin": p.asin,
                    "title": p.title,
                    "price": float(p.current_price) if p.current_price else None,
                    "current_bsr": p.current_bsr,
                    "review_count": p.review_count,
                    "rating": float(p.rating) if p.rating else None,
                }
                for p in db_products
            ]
            landscape = await svc.analyze_landscape(niche_id=niche_id, products=products_for_analysis, category=keyword)
            await svc.persist_landscape(niche_id, landscape)
            await db.commit()
            logger.info("Competitor refresh complete for niche %d", niche_id)
        except Exception as e:
            logger.warning("Competitor refresh failed for niche %d: %s", niche_id, e)


# ═══════════════════════════════════════════════════════════════════════════
# 5. Data Cleanup
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(name="app.workers.tasks.cleanup_old_data")
def cleanup_old_data():
    """Clean up old BSR/price history beyond retention period."""
    logger.info("Starting data cleanup")
    _run_async(_cleanup_async())


async def _cleanup_async():
    """Delete BSR and price history older than 90 days."""
    from app.models.bsr_history import BSRHistory
    from app.models.price_history import PriceHistory

    cutoff = datetime.now(timezone.utc) - timedelta(days=90)
    session_factory = _get_session_factory()

    async with session_factory() as db:
        # Delete old BSR history
        from sqlalchemy import delete
        bsr_result = await db.execute(
            delete(BSRHistory).where(BSRHistory.time < cutoff)
        )
        # Delete old price history
        price_result = await db.execute(
            delete(PriceHistory).where(PriceHistory.time < cutoff)
        )
        await db.commit()

        logger.info(
            "Cleanup complete: removed %d BSR rows, %d price rows",
            bsr_result.rowcount,
            price_result.rowcount,
        )


# ═══════════════════════════════════════════════════════════════════════════
# 6. Daily Sales Velocity Computation
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(name="app.workers.tasks.compute_velocity_snapshots")
def compute_velocity_snapshots():
    """Compute daily velocity snapshots for all tracked products (daily beat task)."""
    logger.info("Starting daily velocity computation")
    _run_async(_compute_velocity_all_async())


async def _compute_velocity_all_async():
    """Compute velocity snapshots for all products in completed niches."""
    from app.models.niche import Niche
    from app.models.product import Product
    from app.services.sales_velocity_service import SalesVelocityService

    session_factory = _get_session_factory()
    async with session_factory() as db:
        # Get all completed niches
        stmt = select(Niche.id, Niche.primary_keyword, Niche.marketplace).where(
            Niche.status == "completed"
        )
        niches = (await db.execute(stmt)).all()

        total_computed = 0
        for niche_id, keyword, marketplace in niches:
            product_stmt = select(Product).where(Product.niche_id == niche_id)
            products = (await db.execute(product_stmt)).scalars().all()

            velocity_svc = SalesVelocityService(db)
            for product in products:
                try:
                    velocity_data = await velocity_svc.compute_daily_velocity(
                        product_id=product.id,
                        category=keyword,
                        marketplace=marketplace or "US",
                    )

                    if velocity_data.get("estimated_daily_sales") is not None:
                        await velocity_svc.save_velocity_snapshot(
                            product_id=product.id,
                            asin=product.asin,
                            velocity_data=velocity_data,
                        )

                        # Update product with latest estimate
                        product.estimated_daily_sales = round(velocity_data["estimated_daily_sales"])

                        # Determine trend from recent snapshots
                        timeseries = await velocity_svc.get_velocity_timeseries(product.id, days=7)
                        if len(timeseries) >= 3:
                            recent = [t["estimated_daily_sales"] for t in timeseries[-3:] if t["estimated_daily_sales"]]
                            earlier = [t["estimated_daily_sales"] for t in timeseries[:3] if t["estimated_daily_sales"]]
                            if recent and earlier:
                                avg_recent = sum(recent) / len(recent)
                                avg_earlier = sum(earlier) / len(earlier)
                                if avg_earlier > 0:
                                    change = (avg_recent - avg_earlier) / avg_earlier
                                    if change > 0.1:
                                        product.sales_velocity_trend = "increasing"
                                    elif change < -0.1:
                                        product.sales_velocity_trend = "decreasing"
                                    else:
                                        product.sales_velocity_trend = "stable"

                        total_computed += 1
                except Exception as e:
                    logger.debug("Velocity computation failed for product %d: %s", product.id, e)

        await db.commit()
        logger.info("Velocity computation complete: %d snapshots created", total_computed)


# ═══════════════════════════════════════════════════════════════════════════
# Helper functions for the analysis pipeline
# ═══════════════════════════════════════════════════════════════════════════
async def _update_niche_status(niche_id: int, status: str, error: str | None = None):
    """Update the niche status in the DB."""
    from app.models.niche import Niche

    session_factory = _get_session_factory()
    async with session_factory() as db:
        values = {"status": status}
        if error:
            values["last_error"] = error[:MAX_STORED_ERROR_CHARS]
        await db.execute(update(Niche).where(Niche.id == niche_id).values(**values))
        await db.commit()


async def _scrape_search_results(scraper: "ScraperService", keyword: str, marketplace: str) -> list[dict]:
    """Return search-result product dicts for *keyword*.

    Prefers SP-API catalog search (legal, unblockable) when credentials are configured,
    enriched with price/rating/badges from page 1 of the SERP. Falls back to a full
    3-page SERP scrape when SP-API isn't configured, errors, or returns too few results
    to trust on its own. Returns [] if that fallback scrape also fails.
    """
    from app.workers.pipeline_steps.product_source import product_source_for

    if product_source_for(Settings()) == "spapi":
        spapi_products = await _search_via_spapi(scraper, keyword, marketplace)
        if spapi_products is not None:
            return spapi_products

    try:
        return await scraper.scrape_search_results(keyword, pages=SERP_FALLBACK_PAGES)
    except WrongMarketplaceError:
        # NOTE: an empty result here would be reported as "no products found", which hides
        # the real cause (a geo-redirect) and triggers retries that cannot succeed.
        raise
    except Exception as e:
        logger.warning("Search scraping failed for '%s': %s", keyword, e)
        return []


async def _search_via_spapi(scraper: "ScraperService", keyword: str, marketplace: str) -> list[dict] | None:
    """Search the SP-API catalog and enrich from page 1 of the SERP. Returns None to signal a full-scrape fallback."""
    from app.workers.pipeline_steps.product_source import merge_serp_enrichment

    settings = Settings()
    spapi = _build_spapi_client(settings, marketplace)
    try:
        catalog_items = await spapi.search_catalog_products(keyword)
    except Exception as e:
        logger.warning("SP-API catalog search failed for '%s', falling back to scraping: %s", keyword, e)
        return None
    finally:
        await spapi.close()

    if len(catalog_items) < MIN_SPAPI_SEARCH_RESULTS:
        return None

    for position, item in enumerate(catalog_items, start=1):
        item["position"] = position

    try:
        serp_page_one = await scraper.scrape_search_results(keyword, pages=SERP_ENRICHMENT_PAGES)
    except Exception as e:
        logger.warning("SERP enrichment scrape failed for '%s': %s", keyword, e)
        serp_page_one = []

    return merge_serp_enrichment(catalog_items, serp_page_one)


async def _save_products(db: AsyncSession, niche_id: int, products_data: list[dict]) -> list[int]:
    """Save scraped products to the database, return list of product IDs."""
    from app.models.product import Product

    product_ids = []
    for p in products_data:
        asin = p.get("asin")
        if not asin:
            continue

        # Check if product already exists (asin is globally unique)
        stmt = select(Product).where(Product.asin == asin)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            # Update existing — reassign to current niche
            existing.niche_id = niche_id
            if p.get("title"):
                existing.title = p["title"]
            if p.get("price") is not None:
                existing.current_price = p["price"]
            if p.get("bsr") is not None:
                existing.current_bsr = p["bsr"]
            if p.get("rating") is not None:
                existing.rating = p["rating"]
            if p.get("review_count") is not None:
                existing.review_count = p["review_count"]
            if p.get("image_url"):
                existing.image_url = p["image_url"]
            if p.get("position") is not None:
                existing.search_position = p["position"]
            if p.get("is_sponsored") is not None:
                existing.is_sponsored = p["is_sponsored"]
            if p.get("is_amazon_choice") is not None:
                existing.is_amazon_choice = p["is_amazon_choice"]
            if p.get("is_best_seller") is not None:
                existing.is_best_seller = p["is_best_seller"]
            if p.get("is_fba") is not None:
                existing.is_fba = p["is_fba"]
            product_ids.append(existing.id)
        else:
            product = Product(
                niche_id=niche_id,
                asin=asin,
                title=p.get("title", ""),
                current_price=p.get("price"),
                current_bsr=p.get("bsr"),
                rating=p.get("rating"),
                review_count=p.get("review_count", 0),
                image_url=p.get("image_url"),
                search_position=p.get("position"),
                is_sponsored=p.get("is_sponsored"),
                is_amazon_choice=p.get("is_amazon_choice"),
                is_best_seller=p.get("is_best_seller"),
                is_fba=p.get("is_fba"),
            )
            db.add(product)
            await db.flush()
            product_ids.append(product.id)

    await db.commit()
    return product_ids


def _stored_product_as_detail(product) -> dict:
    """Turn a stored Product row into the same dict shape a fresh detail-page scrape gives.

    WHY: the sub-niche flow reuses the parent niche's products instead of
    re-scraping, and category/Amazon-share/BSR signals read these keys.
    """
    return {
        "asin": product.asin,
        "title": product.title,
        "brand": product.brand,
        "image_url": product.image_url,
        "price": float(product.current_price) if product.current_price is not None else None,
        "rating": float(product.rating) if product.rating is not None else None,
        "review_count": product.review_count,
        "bsr": product.current_bsr,
        "current_bsr": product.current_bsr,
        "bsr_category": product.bsr_category,
        "seller_id": product.seller_id,
        "date_first_available": product.date_first_available.isoformat() if product.date_first_available else None,
    }


def _extract_avg_dimensions(detailed_products: list[dict]) -> dict:
    """Extract and average product dimensions/weight from scraped product data.

    Parses dimension strings like "10.2 x 6.1 x 4.0 inches" and weight values
    from each product, then returns averaged values.  Falls back to sensible
    defaults when no parseable data is found.
    """
    import re

    from app.core.units import parse_weight_lb

    DEFAULT_DIMS ={"length": 10, "width": 6, "height": 4, "weight_lb": 1.1}

    lengths, widths, heights, weights = [], [], [], []

    for product in detailed_products:
        # --- dimensions ---
        dim_str = product.get("dimensions") or product.get("product_dimensions") or ""
        if dim_str:
            # Match patterns like "10.2 x 6.1 x 4.0 inches" or "10.2 x 6.1 x 4"
            match = re.search(
                r"([\d.]+)\s*x\s*([\d.]+)\s*x\s*([\d.]+)",
                dim_str,
                re.IGNORECASE,
            )
            if match:
                try:
                    lengths.append(float(match.group(1)))
                    widths.append(float(match.group(2)))
                    heights.append(float(match.group(3)))
                except (ValueError, IndexError):
                    pass

        # --- weight ---
        weight_val = (
            product.get("weight")
            or product.get("product_weight_lbs")
            or product.get("weight_lbs")
        )
        weight_lb = parse_weight_lb(weight_val)
        if weight_lb is not None:
            weights.append(weight_lb)

    if not lengths:
        return DEFAULT_DIMS

    return {
        "length": round(sum(lengths) / len(lengths), 2),
        "width": round(sum(widths) / len(widths), 2),
        "height": round(sum(heights) / len(heights), 2),
        "weight_lb": round(sum(weights) / len(weights), 2) if weights else DEFAULT_DIMS["weight_lb"],
    }


def _build_competitor_metadata(detailed_products: list[dict]) -> list[dict]:
    """Build compact competitor metadata for the blueprint service."""
    return [
        {
            "asin": p.get("asin", ""),
            "title": p.get("title", ""),
            "price": p.get("price", 0),
            "rating": p.get("rating", 0),
            "review_count": p.get("review_count", 0),
            "bsr": p.get("current_bsr") or p.get("bsr", 0),
        }
        for p in detailed_products
        if p.get("asin")
    ]


async def _analyze_suppliers(
    db: AsyncSession, niche_id: int, metrics: dict, marketplace: str = "US",
    fob_unit_cost: float | None = None, weight_kg: float = 0.5,
) -> dict | None:
    """Landed cost + margins. Uses the median scraped 1688 FOB price when we have one."""
    from app.core.category_mapping import category_slugs
    from app.services.supplier_service import SupplierService

    svc = SupplierService(marketplace=marketplace)
    avg_price = metrics.get("avg_price", 30)
    unit_cost = fob_unit_cost or avg_price * FOB_FALLBACK_SHARE_OF_PRICE
    metrics["fob_unit_cost_estimated"] = fob_unit_cost is None
    if fob_unit_cost is None:
        logger.info("No supplier prices scraped; estimating FOB as %.0f%% of price", FOB_FALLBACK_SHARE_OF_PRICE * 100)
    duty_slug, _ = category_slugs(metrics.get("category"))

    landed = svc.calculate_landed_cost(unit_cost=unit_cost, quantity=500, weight_kg=weight_kg, category=duty_slug)
    margin = svc.calculate_margins(
        selling_price=avg_price, landed_cost=landed,
        fba_fulfillment_fee=metrics.get("fba_fees", 5),
        ppc_cost_per_unit=metrics.get("avg_cpc", 1.5) / 0.12,
    )
    metrics["fob_unit_cost"] = round(unit_cost, 4)
    metrics["landed_cost"] = landed.total_cost_to_amazon
    metrics["pre_ppc_margin_pct"] = margin["pre_ppc_margin_pct"]
    metrics["post_ppc_margin_pct"] = margin["post_ppc_margin_pct"]
    return {"landed_cost": {"total_landed_cost_usd_per_unit": landed.total_cost_to_amazon}, "margins": margin}


# CNY to USD conversion rate
_CNY_TO_USD_RATE = 7.2

# Product weight is scraped in pounds; landed-cost/shipping math needs kilograms.
LB_TO_KG = 0.4536

# When no 1688 supplier prices were scraped, estimate FOB as this share of the average listing price.
FOB_FALLBACK_SHARE_OF_PRICE = 0.15

# FOB is typically about this share of total landed cost; used only when we have neither a
# scraped supplier price nor a computed landed cost to work from.
FOB_SHARE_OF_LANDED_FALLBACK = 0.55
DEFAULT_LANDED_COST_USD = 8


def _calculate_supplier_score(supplier: dict) -> float:
    """Calculate a basic supplier score (0-100) from scraped data.

    Scoring breakdown:
        - Transaction count: up to 30 points
        - Years in business: up to 25 points
        - Verification badge: 20 points
        - Response rate: up to 15 points
        - Has MOQ listed: 10 points
    """
    score = 0.0

    # Transaction count (up to 30 pts)
    txn = supplier.get("transaction_count") or 0
    if txn >= 10000:
        score += 30
    elif txn >= 1000:
        score += 25
    elif txn >= 100:
        score += 18
    elif txn > 0:
        score += 10

    # Years in business (up to 25 pts)
    years = supplier.get("years_in_business") or 0
    if years >= 10:
        score += 25
    elif years >= 5:
        score += 20
    elif years >= 3:
        score += 15
    elif years >= 1:
        score += 8

    # Verification badge (20 pts)
    if supplier.get("is_verified"):
        score += 20

    # Response rate (up to 15 pts)
    rate = supplier.get("response_rate") or 0
    if rate >= 90:
        score += 15
    elif rate >= 70:
        score += 10
    elif rate > 0:
        score += 5

    # Has MOQ listed (10 pts — indicates professional listing)
    if supplier.get("moq") is not None:
        score += 10

    return min(score, 100.0)


async def _save_suppliers(
    db: AsyncSession, niche_id: int, scraped_suppliers: list[dict]
) -> list[int]:
    """Save scraped 1688 supplier data to the Supplier model.

    Converts CNY prices to USD and computes a basic supplier score.
    Returns the list of created supplier IDs.
    """
    from app.models.supplier import Supplier

    supplier_ids: list[int] = []

    for s in scraped_suppliers:
        supplier_name = s.get("supplier_name")
        if not supplier_name:
            continue

        # Convert CNY prices to USD
        price_min_cny = s.get("price_min")
        price_max_cny = s.get("price_max")
        fob_min = round(price_min_cny / _CNY_TO_USD_RATE, 4) if price_min_cny else None
        fob_max = round(price_max_cny / _CNY_TO_USD_RATE, 4) if price_max_cny else None

        # Calculate supplier score
        score = _calculate_supplier_score(s)
        s["supplier_score"] = score

        supplier = Supplier(
            niche_id=niche_id,
            supplier_name=supplier_name,
            country="China",
            city=s.get("location"),
            alibaba_url=s.get("product_url"),
            years_in_business=s.get("years_in_business"),
            is_gold_supplier=s.get("is_verified", False),
            is_verified=s.get("is_verified", False),
            trade_assurance=False,  # 1688 does not use Alibaba Trade Assurance
            moq=s.get("moq"),
            fob_price_min=fob_min,
            fob_price_max=fob_max,
            transaction_volume=s.get("transaction_count"),
            response_rate=s.get("response_rate"),
            supplier_score=score,
        )
        db.add(supplier)
        await db.flush()
        supplier_ids.append(supplier.id)

    await db.commit()
    logger.info("Saved %d suppliers for niche %d from 1688", len(supplier_ids), niche_id)
    return supplier_ids


def _derive_product_signals(detailed_products: list[dict], marketplace: str) -> dict:
    """Derive category, strong-seller count, Amazon-seller share, and avg rating from scraped products."""
    from app.core.marketplace import get_marketplace
    from app.services.market_signals import amazon_seller_pct, count_strong_sellers, derive_category

    ratings = [float(p["rating"]) for p in detailed_products if p.get("rating")]
    return {
        "marketplace": marketplace,
        "category": derive_category(detailed_products),
        "strong_seller_count": count_strong_sellers(detailed_products),
        "amazon_seller_pct": amazon_seller_pct(detailed_products, get_marketplace(marketplace).amazon_seller_id),
        "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else 0,
    }


def _build_base_metrics(
    competitor_landscape: dict | None,
    detailed_products: list[dict],
    keyword_research_summary: dict | None = None,
    marketplace: str = "US",
) -> dict:
    """Build base metrics dict from competitor data and scraped products."""
    metrics = {
        "avg_price": 0,
        # NOTE: avg_bsr is deliberately NOT seeded. A seeded 0 reads as rank #0 (the best
        # possible) to the scorer, so a BSR blackout would score as top demand. Leaving it
        # absent lets ScoringService's m.get("avg_bsr", 99999) treat "unknown" as poor demand.
        "estimated_monthly_sales": 0,
        "avg_rating": 0,
        "avg_review_count": 0,
        "median_competitor_reviews": 0,
        "search_volume": 0,
        "avg_listing_quality": 50,
        "strong_seller_count": 0,
        "amazon_seller_pct": 0,
        "is_restricted_category": False,
        "ip_risk_detected": False,
        "is_seasonal": False,
        "avg_cpc": 1.5,
        "fba_fees": 5.0,
    }
    metrics.update(_derive_product_signals(detailed_products, marketplace))

    # Use real keyword research data if available
    if keyword_research_summary:
        top_kws = keyword_research_summary.get("top_keywords", [])
        if top_kws:
            metrics["search_volume"] = top_kws[0].get("search_volume", 0)
        else:
            metrics["search_volume"] = keyword_research_summary.get("avg_search_volume", 0)
        metrics["relevant_keyword_count"] = keyword_research_summary.get("total_keywords_discovered", 0)

        # Estimate avg_cpc from volume tier distribution
        tier_dist = keyword_research_summary.get("volume_tier_distribution", {})
        if tier_dist.get("very_high", 0) > 0 or tier_dist.get("high", 0) > 0:
            metrics["avg_cpc"] = 2.00
        elif tier_dist.get("medium", 0) > 0:
            metrics["avg_cpc"] = 1.40
        else:
            metrics["avg_cpc"] = 0.90

    if competitor_landscape:
        price_stats = competitor_landscape.get("price_stats", {})
        review_stats = competitor_landscape.get("review_stats", {})
        rating_stats = competitor_landscape.get("rating_stats", {})
        metrics.update({
            "avg_price": price_stats.get("avg", competitor_landscape.get("avg_price", 0)),
            "avg_rating": rating_stats.get("avg", competitor_landscape.get("avg_rating", 0)),
            "avg_review_count": review_stats.get("avg", competitor_landscape.get("avg_review_count", 0)),
            "median_competitor_reviews": review_stats.get("median", competitor_landscape.get("median_reviews", 0)),
            "avg_listing_quality": competitor_landscape.get("avg_listing_quality", 50),
            "estimated_monthly_sales": competitor_landscape.get("estimated_monthly_sales", 0),
        })
        # Only set avg_bsr from a real measurement; never seed it (see the note above).
        if competitor_landscape.get("avg_bsr"):
            metrics["avg_bsr"] = competitor_landscape["avg_bsr"]

    # Fallback: if avg_price is still 0, compute from detailed products
    if not metrics["avg_price"] and detailed_products:
        prices = [p.get("price") for p in detailed_products if p.get("price")]
        if prices:
            metrics["avg_price"] = round(sum(prices) / len(prices), 2)
            logger.info(
                "Computed avg_price from %d detailed products: $%.2f",
                len(prices), metrics["avg_price"],
            )

    # Fallback: if avg_bsr is still unknown, compute from detailed products
    if not metrics.get("avg_bsr") and detailed_products:
        bsrs = [p.get("current_bsr") for p in detailed_products if p.get("current_bsr")]
        if bsrs:
            metrics["avg_bsr"] = round(sum(bsrs) / len(bsrs))

    # Fallback: if avg_review_count is still 0, compute from detailed products
    if not metrics["avg_review_count"] and detailed_products:
        reviews = [p.get("review_count") for p in detailed_products if p.get("review_count")]
        if reviews:
            metrics["avg_review_count"] = round(sum(reviews) / len(reviews))

    # Fallback: if the competitor pass gave no median review count, compute it from the
    # detailed products. Without this the review-moat hard filter reads 0 and always passes.
    if not metrics["median_competitor_reviews"] and detailed_products:
        review_counts = [p.get("review_count") for p in detailed_products if p.get("review_count")]
        if review_counts:
            metrics["median_competitor_reviews"] = round(median(review_counts))

    # Compute estimated_monthly_sales from BSR using regression model
    if not metrics["estimated_monthly_sales"] and metrics.get("avg_bsr"):
        from app.core.bsr_regression import BSRSalesEstimator
        estimator = BSRSalesEstimator(marketplace=metrics.get("marketplace", "US"))
        metrics["estimated_monthly_sales"] = estimator.estimate_monthly_sales(
            bsr=int(metrics["avg_bsr"]),
            category=metrics.get("category", "default"),
        )
        logger.info(
            "Estimated monthly sales from BSR %d: %d units",
            metrics["avg_bsr"], metrics["estimated_monthly_sales"],
        )

    # WHY: computed before the 300-unit fallback below, so a made-up sales
    # number never turns into a made-up revenue. The regression estimate is
    # for one typical listing, which makes this revenue per seller.
    if metrics["estimated_monthly_sales"] > 0 and metrics["avg_price"] > 0:
        metrics["monthly_revenue_per_seller"] = round(metrics["estimated_monthly_sales"] * metrics["avg_price"])

    # Fallback: no BSR to estimate from, so assume a mid-range figure. Flagged so the
    # brief discloses it as an assumption (see pipeline_steps/assumptions.py).
    if not metrics["estimated_monthly_sales"]:
        metrics["estimated_monthly_sales"] = 300
        metrics["sales_estimated"] = True
        logger.info("Using fallback estimated_monthly_sales: 300")

    return metrics


def _base_case_break_even_week(financial_summary: dict) -> int:
    """The week the base-case forecast turns cumulative profit positive.

    The forecast returns None when that never happens inside its horizon; we
    report the horizon itself, which the scorer treats as its worst case.
    """
    break_even_week = financial_summary.get("base", {}).get("break_even_week")
    return break_even_week if break_even_week is not None else FORECAST_HORIZON_WEEKS


def _enrich_metrics(
    metrics: dict,
    competitor_landscape: dict | None,
    ppc_strategy: dict | None,
    review_strategy: dict | None,
    supplier_data: dict | None,
):
    """Enrich the metrics dict with data from all analysis services."""
    if competitor_landscape:
        metrics.setdefault("avg_review_count", competitor_landscape.get("avg_reviews"))
        metrics.setdefault("median_competitor_reviews", competitor_landscape.get("median_reviews", competitor_landscape.get("avg_reviews")))
        if competitor_landscape.get("avg_listing_quality") is not None:
            metrics.setdefault("avg_listing_quality", competitor_landscape.get("avg_listing_quality"))
        if competitor_landscape.get("high_vulnerability_count") is not None:
            metrics.setdefault("high_vulnerability_count", competitor_landscape.get("high_vulnerability_count"))

    if ppc_strategy:
        from app.workers.pipeline_steps.ppc import ppc_metrics_from_strategy
        metrics.update(ppc_metrics_from_strategy(ppc_strategy))

    if review_strategy:
        metrics["review_threshold"] = review_strategy.get("review_threshold", {}).get("threshold", 50)
        metrics["weeks_to_review_threshold"] = review_strategy.get("timeline", {}).get("organic_weeks", 52)

    if supplier_data:
        margins = supplier_data.get("margins", {})
        metrics["pre_ppc_margin_pct"] = margins.get("pre_ppc_margin_pct", metrics.get("pre_ppc_margin_pct", 0))
        metrics["post_ppc_margin_pct"] = margins.get("post_ppc_margin_pct", metrics.get("post_ppc_margin_pct", 0))

        landed = supplier_data.get("landed_cost", {})
        metrics["landed_cost"] = landed.get("total_landed_cost_usd_per_unit", metrics.get("landed_cost", 0))

    # Fill any scoring inputs we could not measure, and record each one as a
    # data gap instead of a silent fake default (see assumptions.py).
    from app.workers.pipeline_steps.assumptions import apply_assumed_defaults
    apply_assumed_defaults(metrics)


def _has_chinese(text: str | None) -> bool:
    """Return True if text contains Chinese characters."""
    if not text:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", text))


async def _translate_supplier_fields(llm_client, suppliers: list[dict]) -> list[dict]:
    """Detect Chinese text in supplier fields and batch-translate via LLM."""
    # Collect all Chinese strings that need translation
    texts_to_translate: list[str] = []
    field_map: list[tuple[int, str]] = []  # (supplier_index, field_name)

    translatable_fields = [
        "supplier_name", "product_title", "location", "description",
        "product_name", "shop_name", "category",
    ]

    for i, s in enumerate(suppliers):
        for field in translatable_fields:
            val = s.get(field)
            if _has_chinese(val):
                texts_to_translate.append(val)
                field_map.append((i, field))

    if not texts_to_translate:
        return suppliers

    # Batch translate via LLM (chunks of 20)
    chunk_size = 20
    translated: list[str] = []

    for start in range(0, len(texts_to_translate), chunk_size):
        chunk = texts_to_translate[start : start + chunk_size]
        numbered = "\n".join(f"{j+1}. {t}" for j, t in enumerate(chunk))
        prompt = (
            "Translate the following Chinese text to English. "
            "Return ONLY the translations, one per line, numbered to match.\n\n"
            f"{numbered}"
        )
        try:
            result = await llm_client.generate(prompt)
            lines = [l.strip() for l in result.strip().split("\n") if l.strip()]
            # Parse numbered lines
            parsed: list[str] = []
            for line in lines:
                # Strip leading number + dot/parenthesis
                cleaned = re.sub(r"^\d+[\.\)\]]\s*", "", line)
                parsed.append(cleaned)
            # WHY: translations are matched back to fields by position across all chunks.
            # If the LLM merges, splits, or drops a line, this chunk's count is wrong and
            # every later chunk would be written to the wrong supplier/field. Fall back to
            # the untranslated chunk on a count mismatch so the misalignment can't propagate.
            if len(parsed) != len(chunk):
                logger.warning(
                    "Translation chunk returned %d lines for %d inputs; keeping originals",
                    len(parsed), len(chunk),
                )
                translated.extend(chunk)
            else:
                translated.extend(parsed)
        except Exception as e:
            logger.warning("Translation chunk failed: %s", e)
            # Keep originals for failed chunks
            translated.extend(chunk)

    # Apply translations back
    for idx, (sup_idx, field_name) in enumerate(field_map):
        if idx < len(translated) and translated[idx]:
            suppliers[sup_idx][field_name] = translated[idx]

    logger.info("Translated %d supplier fields from Chinese to English", len(field_map))
    return suppliers
