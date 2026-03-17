"""Celery task definitions for Omniscient background processing."""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.core.exceptions import ScrapingError
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async DB session helper — Celery workers run in sync context, so we need
# our own engine + event loop to run async DB operations.
# ---------------------------------------------------------------------------


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Create a fresh async engine + session factory for each call.

    We intentionally do NOT cache the engine across calls because Celery's
    prefork workers create new event loops for each task, and asyncpg
    connection pools are bound to the loop that created them.
    """
    settings = Settings()
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=5,
    )
    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


def _run_async(coro):
    """Run an async coroutine in a new event loop (safe for Celery workers)."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_llm_client():
    """Create an LLM client from settings. Returns None if no API key is configured."""
    from app.llm.factory import create_llm_client
    try:
        return create_llm_client(Settings())
    except Exception as e:
        logger.warning("LLM client not available (LLM-powered steps will be skipped): %s", e)
        return None


# ═══════════════════════════════════════════════════════════════════════════
# 1. Full Niche Analysis Pipeline
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(bind=True, name="app.workers.tasks.run_full_analysis", max_retries=2)
def run_full_analysis(self, niche_id: int, keyword: str, options: dict | None = None, product_asins: list[str] | None = None):
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
    product_asins : list[str] | None
        If provided, skip scraping and filter to only these ASINs (sub-niche flow).
    """
    options = options or {}
    logger.info("Starting full analysis for niche %d: %s", niche_id, keyword)

    try:
        return _run_async(_run_full_analysis_async(self, niche_id, keyword, options, product_asins=product_asins))
    except Exception as exc:
        logger.exception("Full analysis failed for niche %d", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", str(exc)))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


# ═══════════════════════════════════════════════════════════════════════════
# 1b. Discovery Phase (sub-niche detection)
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(bind=True, name="app.workers.tasks.run_discovery", max_retries=2)
def run_discovery(self, niche_id: int, keyword: str, options: dict | None = None):
    """
    Phase A: Scrape products, detect heterogeneity, optionally cluster sub-niches.

    Returns
    -------
    dict
        If narrow: {"is_broad": false, "niche_id": N}
        If broad:  {"is_broad": true, "sub_niches": [...], "niche_id": N, "heterogeneity": {...}}
    """
    options = options or {}
    logger.info("Starting discovery for niche %d: %s", niche_id, keyword)

    try:
        return _run_async(_run_discovery_async(self, niche_id, keyword, options))
    except Exception as exc:
        logger.exception("Discovery failed for niche %d", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", str(exc)))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_discovery_async(task, niche_id: int, keyword: str, options: dict):
    """Async implementation of the discovery pipeline."""
    from app.models.niche import Niche

    session_factory = _get_session_factory()
    llm_client = _get_llm_client()

    async with session_factory() as db:
        # Update status to discovering
        await db.execute(
            update(Niche).where(Niche.id == niche_id).values(status="discovering")
        )
        await db.commit()

        # ── Step 1: Scrape search results ──────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_search", "progress": 5})
        products_data = await _scrape_search_results(keyword)

        if not products_data:
            await _update_niche_status(niche_id, "failed", "No products found for keyword")
            raise ScrapingError(f"No products found for keyword '{keyword}'")

        # ── Step 2: Save products ──────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 10})
        await _save_products(db, niche_id, products_data)

        # ── Step 3: Scrape top product details ─────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 15})
        detailed_products = await _scrape_product_details(db, niche_id, products_data[:20])

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


async def _run_full_analysis_async(task, niche_id: int, keyword: str, options: dict, product_asins: list[str] | None = None):
    """Async implementation of the full analysis pipeline."""
    from app.models.niche import Niche
    from app.models.product import Product

    session_factory = _get_session_factory()
    llm_client = _get_llm_client()

    async with session_factory() as db:
        # Update status to analyzing
        await db.execute(
            update(Niche).where(Niche.id == niche_id).values(status="analyzing")
        )
        await db.commit()

        if product_asins:
            # ── Sub-niche flow: load products from parent niche by ASIN ──
            task.update_state(state="PROGRESS", meta={"step": "loading_products", "progress": 5})

            # Look up the parent niche to get its products
            niche_row = (await db.execute(select(Niche).where(Niche.id == niche_id))).scalar_one_or_none()
            parent_id = niche_row.parent_niche_id if niche_row else None

            # Load products from DB that match the given ASINs
            product_query = select(Product).where(Product.asin.in_(product_asins))
            if parent_id:
                product_query = product_query.where(Product.niche_id == parent_id)
            result = await db.execute(product_query)
            db_products = result.scalars().all()

            # Reassign products to child niche
            for p in db_products:
                p.niche_id = niche_id
            await db.flush()
            await db.commit()

            products_data = [
                {
                    "asin": p.asin,
                    "title": p.title,
                    "price": float(p.current_price) if p.current_price else None,
                    "bsr": p.current_bsr,
                    "rating": float(p.rating) if p.rating else None,
                    "review_count": p.review_count,
                    "brand": p.brand if hasattr(p, "brand") else None,
                }
                for p in db_products
            ]
            detailed_products = products_data  # Already have detail data
            task.update_state(state="PROGRESS", meta={"step": "products_scraped", "progress": 30})

        else:
            # ── Standard flow: scrape from scratch ────────────────────────

            # ── Step 1: Scrape search results ──────────────────────────────
            task.update_state(state="PROGRESS", meta={"step": "scraping_search", "progress": 5})
            products_data = await _scrape_search_results(keyword)

            if not products_data:
                await _update_niche_status(niche_id, "failed", "No products found for keyword")
                raise ScrapingError(f"No products found for keyword '{keyword}'")

            # ── Step 2: Save products and scrape details ───────────────────
            task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 15})
            product_ids = await _save_products(db, niche_id, products_data)

            # Scrape individual product pages for detailed data
            detailed_products = await _scrape_product_details(db, niche_id, products_data[:20])

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
                                "has_a_plus", "has_brand_story", "seller_id"):
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

        # ── Step 2c: Extract reviews from product page data ─────────
        # Reviews are embedded in product detail pages (top reviews section),
        # extracted during scrape_product_page(). No separate page loads needed.
        task.update_state(state="PROGRESS", meta={"step": "review_extraction", "progress": 32})
        from app.models.review import Review as ReviewModel
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

            for review_data in page_reviews:
                # Check for duplicate by review_id
                if review_data.get("review_id"):
                    existing = await db.execute(
                        select(ReviewModel.id).where(
                            ReviewModel.review_id == review_data["review_id"]
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none():
                        continue

                review_obj = ReviewModel(
                    product_id=product_obj.id,
                    asin=asin,
                    review_id=review_data.get("review_id"),
                    rating=review_data.get("rating", 0),
                    title=review_data.get("title", ""),
                    body=review_data.get("body", ""),
                    review_date=review_data.get("review_date"),
                    verified_purchase=review_data.get("verified_purchase", False),
                    helpful_votes=review_data.get("helpful_votes", 0),
                    is_vine=review_data.get("is_vine", False),
                )
                db.add(review_obj)
                reviews_scraped += 1
            await db.flush()

        logger.info("Extracted %d reviews from product pages", reviews_scraped)

        # ── Step 3: Competitor analysis ────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "competitor_analysis", "progress": 35})
        from app.services.competitor_service import CompetitorService
        competitor_svc = CompetitorService(db, llm_client)

        competitor_landscape = await competitor_svc.analyze_landscape(
            niche_id=niche_id,
            products=products_data[:20],
            category=keyword,
        )

        # ── Step 4: Analyze reviews (top 10 products) ──────────────────
        task.update_state(state="PROGRESS", meta={"step": "review_analysis", "progress": 38})
        from app.services.review_analyzer import ReviewAnalyzer
        review_analyzer = ReviewAnalyzer(llm_client)

        review_insights = None
        all_reviews = await _collect_reviews(db, niche_id)
        if all_reviews:
            try:
                review_insights = await review_analyzer.analyze_reviews(all_reviews)
            except Exception as e:
                logger.warning("Review analysis failed: %s", e)

        # ── Step 4b: Review Intelligence (deep cross-product synthesis) ──
        task.update_state(state="PROGRESS", meta={"step": "review_intelligence", "progress": 42})
        review_intelligence = None
        competitor_reviews_map = await _collect_competitor_reviews(db, niche_id)
        product_titles_map = {
            p.get("asin", ""): p.get("title", "")
            for p in detailed_products if p.get("asin")
        }
        if competitor_reviews_map and llm_client:
            try:
                # Build flat list of all review dicts for the intelligence method
                all_review_dicts = []
                for reviews_list in competitor_reviews_map.values():
                    all_review_dicts.extend(reviews_list)

                review_intelligence = await review_analyzer.generate_review_intelligence(
                    all_reviews=all_review_dicts,
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
                    _build_base_metrics(competitor_landscape, detailed_products),
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
        # competitor_reviews_map already collected in step 4b above
        if not competitor_reviews_map:
            competitor_reviews_map = await _collect_competitor_reviews(db, niche_id)
        competitor_meta = _build_competitor_metadata(detailed_products)
        if competitor_reviews_map:
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

        supplier_scraper = SupplierScraper(cookie_manager=cookie_manager)

        scraped_suppliers: list[dict] = []
        try:
            scraped_suppliers = await supplier_scraper.search_suppliers(keyword, max_results=10)
        except Exception as e:
            logger.warning("Supplier scraping failed: %s", e)

        # Save scraped suppliers to DB
        if scraped_suppliers:
            await _save_suppliers(db, niche_id, scraped_suppliers)

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
        from app.services.supplier_service import SupplierService
        supplier_svc = SupplierService()

        metrics = _build_base_metrics(competitor_landscape, detailed_products)
        supplier_data = None
        try:
            supplier_data = await _analyze_suppliers(db, niche_id, metrics)
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
        ppc_svc = PPCService(db, llm_client)

        ppc_strategy = None
        try:
            # Build PPC inputs
            break_even_acos = ppc_svc.calculate_break_even_acos(
                selling_price=metrics.get("avg_price") or 30,
                landed_cost=metrics.get("landed_cost") or 8,
                fba_fees=metrics.get("fba_fees") or 5,
            )
            keyword_portfolio = await ppc_svc.build_keyword_portfolio(niche_id=niche_id)
            budget_plan = {
                "daily_budget": metrics.get("ppc_daily_budget") or 30,
                "monthly_budget": (metrics.get("ppc_daily_budget") or 30) * 30,
            }

            ppc_strategy = await ppc_svc.generate_ppc_strategy(
                niche_keyword=keyword,
                keyword_portfolio=keyword_portfolio,
                budget_plan=budget_plan,
                break_even_acos=break_even_acos,
                competitor_landscape=competitor_landscape,
            )
        except Exception as e:
            logger.warning("PPC strategy generation failed: %s", e)

        # ── Step 9: Review strategy ────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "review_strategy", "progress": 72})
        from app.services.review_strategy import ReviewStrategyService
        review_svc = ReviewStrategyService(llm_client)

        review_strategy = None
        try:
            # Gather competitor review counts from products data
            competitor_reviews = [p.get("review_count", 0) for p in products_data[:20] if p.get("review_count")]
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

            # Calculate launch capital
            launch_capital = forecast_svc.calculate_launch_capital(
                landed_cost=metrics.get("landed_cost") or 8,
                initial_order_qty=metrics.get("initial_order_qty") or 500,
                vine_cost=review_strategy.get("vine_plan", {}).get("costs", {}).get("total_vine_cost", 0) if review_strategy else 0,
                ppc_budget_90_days=metrics.get("ppc_budget_90d") or 2700,
            )
            metrics["total_launch_capital"] = launch_capital["total_launch_capital"]
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
        fin_report_svc = FinancialReportService()

        financial_report = None
        try:
            # Estimate FOB cost from landed cost (reverse-engineer)
            fob_estimate = (metrics.get("landed_cost") or 8) * 0.55  # FOB is roughly 55% of landed
            product_dims = _extract_avg_dimensions(detailed_products)
            financial_report = await fin_report_svc.generate_full_report(
                selling_price=metrics.get("avg_price") or 30,
                unit_cost_fob=fob_estimate,
                product_dims=product_dims,
                category=metrics.get("category", "default"),
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
    """Fetch all active niches and track BSR/prices for their products."""
    from app.models.niche import Niche
    from app.models.product import Product

    session_factory = _get_session_factory()
    async with session_factory() as db:
        # Get all completed niches (actively tracked)
        stmt = select(Niche.id).where(Niche.status == "completed")
        result = await db.execute(stmt)
        niche_ids = [row[0] for row in result.all()]

    # Fan out individual tracking tasks
    for niche_id in niche_ids:
        track_bsr_prices.delay(niche_id)

    logger.info("Queued BSR tracking for %d niches", len(niche_ids))


@celery_app.task(name="app.workers.tasks.track_bsr_prices", max_retries=1)
def track_bsr_prices(niche_id: int):
    """Track BSR and prices for all products in a specific niche."""
    logger.info("Tracking BSR/prices for niche %d", niche_id)
    _run_async(_track_bsr_niche_async(niche_id))


async def _track_bsr_niche_async(niche_id: int):
    """Scrape current BSR & price for each product in the niche."""
    from app.models.product import Product
    from app.services.bsr_tracker import BSRTracker

    session_factory = _get_session_factory()
    async with session_factory() as db:
        tracker = BSRTracker(db)

        stmt = select(Product).where(Product.niche_id == niche_id)
        result = await db.execute(stmt)
        products = result.scalars().all()

        for product in products:
            try:
                # Record current BSR
                if product.current_bsr:
                    await tracker.record_bsr(
                        product_id=product.id,
                        asin=product.asin,
                        bsr=product.current_bsr,
                        category_id=product.category_id,
                    )

                # Record current price
                if product.current_price:
                    await tracker.record_price(
                        product_id=product.id,
                        asin=product.asin,
                        price=float(product.current_price),
                    )
            except Exception as e:
                logger.warning("Failed to track product %s: %s", product.asin, e)

        await db.commit()
        logger.info("Tracked %d products in niche %d", len(products), niche_id)


# ═══════════════════════════════════════════════════════════════════════════
# 3. Review Scraping
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(name="app.workers.tasks.scrape_reviews", max_retries=2)
def scrape_reviews(niche_id: int, asin: str, max_pages: int = 5):
    """Scrape reviews for a specific product."""
    logger.info("Scraping reviews for ASIN %s (niche %d)", asin, niche_id)
    _run_async(_scrape_reviews_async(niche_id, asin, max_pages))


async def _scrape_reviews_async(niche_id: int, asin: str, max_pages: int):
    """Scrape and store reviews for a product."""
    from app.models.product import Product
    from app.models.review import Review

    session_factory = _get_session_factory()
    async with session_factory() as db:
        # Find the product
        stmt = select(Product).where(Product.asin == asin, Product.niche_id == niche_id)
        result = await db.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            logger.warning("Product %s not found in niche %d", asin, niche_id)
            return

        # Scrape reviews
        from app.services.scraper_service import ScraperService
        scraper = ScraperService()

        try:
            reviews_data = await scraper.scrape_reviews(asin, max_pages=max_pages)
        except Exception as e:
            logger.warning("Review scraping failed for %s: %s", asin, e)
            return

        # Save to DB
        saved = 0
        for review_data in reviews_data:
            review = Review(
                product_id=product.id,
                reviewer_name=review_data.get("reviewer_name", "Anonymous"),
                rating=review_data.get("rating", 0),
                title=review_data.get("title", ""),
                body=review_data.get("body", ""),
                review_date=review_data.get("date"),
                verified_purchase=review_data.get("verified", False),
                helpful_votes=review_data.get("helpful_votes", 0),
            )
            db.add(review)
            saved += 1

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
        stmt = select(Niche.id, Niche.keyword).where(Niche.status == "completed")
        result = await db.execute(stmt)
        niches = result.all()

    for niche_id, keyword in niches:
        refresh_competitor_data.delay(niche_id, keyword)

    logger.info("Queued competitor refresh for %d niches", len(niches))


@celery_app.task(name="app.workers.tasks.refresh_competitor_data", max_retries=1)
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
            await svc.analyze_landscape(niche_id=niche_id, products=products_for_analysis, category=keyword)
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
# Helper functions for the analysis pipeline
# ═══════════════════════════════════════════════════════════════════════════
async def _update_niche_status(niche_id: int, status: str, error: str | None = None):
    """Update the niche status in the DB."""
    from app.models.niche import Niche

    session_factory = _get_session_factory()
    async with session_factory() as db:
        values = {"status": status}
        if error:
            values["hard_filter_fail_reasons"] = [error]
        await db.execute(update(Niche).where(Niche.id == niche_id).values(**values))
        await db.commit()


async def _scrape_search_results(keyword: str) -> list[dict]:
    """Scrape Amazon search results for a keyword."""
    from app.services.scraper_service import ScraperService

    scraper = ScraperService()
    try:
        return await scraper.scrape_search_results(keyword, pages=3)
    except Exception as e:
        logger.warning("Search scraping failed for '%s': %s", keyword, e)
        return []


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
            )
            db.add(product)
            await db.flush()
            product_ids.append(product.id)

    await db.commit()
    return product_ids


async def _scrape_product_details(
    db: AsyncSession, niche_id: int, products_data: list[dict]
) -> list[dict]:
    """Scrape detailed product pages for enriched data and update DB rows."""
    from app.models.product import Product
    from app.services.scraper_service import ScraperService

    scraper = ScraperService()
    detailed = []

    for p in products_data[:20]:
        asin = p.get("asin")
        if not asin:
            continue
        try:
            detail = await scraper.scrape_product_page(asin)
            if detail:
                detailed.append(detail)
                # Write enriched data back to the product row
                stmt = select(Product).where(Product.asin == asin)
                existing = (await db.execute(stmt)).scalar_one_or_none()
                if existing:
                    if detail.get("title"):
                        existing.title = detail["title"]
                    if detail.get("price") is not None:
                        existing.current_price = detail["price"]
                    if detail.get("rating") is not None:
                        existing.rating = detail["rating"]
                    if detail.get("review_count") is not None:
                        existing.review_count = detail["review_count"]
                    if detail.get("brand"):
                        existing.brand = detail["brand"]
                    if detail.get("current_bsr") is not None:
                        existing.current_bsr = detail["current_bsr"]
                    if detail.get("bsr_category"):
                        existing.bsr_category = detail["bsr_category"]
                    if detail.get("current_subcategory_bsr") is not None:
                        existing.current_subcategory_bsr = detail["current_subcategory_bsr"]
                    if detail.get("subcategory_name"):
                        existing.subcategory_name = detail["subcategory_name"]
                    if detail.get("bullet_count") is not None:
                        existing.bullet_count = detail["bullet_count"]
                    if detail.get("image_count") is not None:
                        existing.image_count = detail["image_count"]
                    existing.has_video = detail.get("has_video", existing.has_video)
                    existing.has_a_plus = detail.get("has_a_plus", existing.has_a_plus)
                    existing.has_brand_story = detail.get("has_brand_story", existing.has_brand_story)
                    if detail.get("seller_id"):
                        existing.seller_id = detail["seller_id"]
                    if detail.get("last_scraped_at"):
                        from datetime import datetime as dt
                        try:
                            existing.last_scraped_at = dt.fromisoformat(detail["last_scraped_at"])
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            logger.warning("Failed to scrape details for %s: %s", asin, e)

    await db.commit()
    return detailed


async def _collect_reviews(db: AsyncSession, niche_id: int) -> list[str]:
    """Collect review text from DB for a niche."""
    from app.models.product import Product
    from app.models.review import Review

    stmt = (
        select(Review.body)
        .join(Product, Review.product_id == Product.id)
        .where(Product.niche_id == niche_id)
        .limit(200)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result.all() if row[0]]


async def _collect_competitor_reviews(db: AsyncSession, niche_id: int) -> dict[str, list[dict]]:
    """Collect reviews grouped by ASIN for all products in a niche."""
    from app.models.product import Product
    from app.models.review import Review

    stmt = (
        select(Product.asin, Review.rating, Review.title, Review.body, Review.verified_purchase, Review.helpful_votes)
        .join(Review, Review.product_id == Product.id)
        .where(Product.niche_id == niche_id)
        .order_by(Product.asin, Review.helpful_votes.desc())
    )
    result = await db.execute(stmt)
    rows = result.all()

    reviews_by_asin: dict[str, list[dict]] = {}
    for asin, rating, title, body, verified, helpful in rows:
        if asin not in reviews_by_asin:
            reviews_by_asin[asin] = []
        # Cap at 30 reviews per ASIN to stay within LLM context limits
        if len(reviews_by_asin[asin]) < 30:
            reviews_by_asin[asin].append({
                "rating": rating,
                "title": title,
                "body": body,
                "verified_purchase": verified,
                "helpful_votes": helpful or 0,
            })

    return reviews_by_asin


def _extract_avg_dimensions(detailed_products: list[dict]) -> dict:
    """Extract and average product dimensions/weight from scraped product data.

    Parses dimension strings like "10.2 x 6.1 x 4.0 inches" and weight values
    from each product, then returns averaged values.  Falls back to sensible
    defaults when no parseable data is found.
    """
    import re

    DEFAULT_DIMS = {"length": 10, "width": 6, "height": 4, "weight_lb": 1.1}

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
        if weight_val is not None:
            try:
                weights.append(float(weight_val))
            except (ValueError, TypeError):
                pass

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


async def _analyze_suppliers(db: AsyncSession, niche_id: int, metrics: dict) -> dict | None:
    """Run supplier analysis."""
    from app.services.supplier_service import SupplierService

    svc = SupplierService()
    avg_price = metrics.get("avg_price", 30)

    # Estimate FOB unit cost: roughly 15% of selling price
    estimated_unit_cost = avg_price * 0.15

    # Calculate landed cost (returns LandedCost dataclass)
    landed = svc.calculate_landed_cost(
        unit_cost=estimated_unit_cost,
        quantity=500,
        weight_kg=0.5,
    )

    # Calculate margins (pass LandedCost object directly)
    margin = svc.calculate_margins(
        selling_price=avg_price,
        landed_cost=landed,
        fba_fulfillment_fee=metrics.get("fba_fees", 5),
        ppc_cost_per_unit=metrics.get("avg_cpc", 1.5) / 0.12,  # CPC / conversion rate
    )

    metrics["landed_cost"] = landed.total_cost_to_amazon
    metrics["pre_ppc_margin_pct"] = margin["pre_ppc_margin_pct"]
    metrics["post_ppc_margin_pct"] = margin["post_ppc_margin_pct"]

    return {"landed_cost": {"total_landed_cost_usd_per_unit": landed.total_cost_to_amazon}, "margins": margin}


# CNY to USD conversion rate
_CNY_TO_USD_RATE = 7.2


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


def _build_base_metrics(competitor_landscape: dict | None, detailed_products: list[dict]) -> dict:
    """Build base metrics dict from competitor data and scraped products."""
    metrics = {
        "avg_price": 0,
        "avg_bsr": 0,
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

    if competitor_landscape:
        price_stats = competitor_landscape.get("price_stats", {})
        review_stats = competitor_landscape.get("review_stats", {})
        rating_stats = competitor_landscape.get("rating_stats", {})
        metrics.update({
            "avg_price": price_stats.get("avg", competitor_landscape.get("avg_price", 0)),
            "avg_bsr": competitor_landscape.get("avg_bsr", 0),
            "avg_rating": rating_stats.get("avg", competitor_landscape.get("avg_rating", 0)),
            "avg_review_count": review_stats.get("avg", competitor_landscape.get("avg_review_count", 0)),
            "median_competitor_reviews": review_stats.get("median", competitor_landscape.get("median_reviews", 0)),
            "avg_listing_quality": competitor_landscape.get("avg_listing_quality", 50),
            "strong_seller_count": competitor_landscape.get("strong_seller_count", 0),
            "amazon_seller_pct": competitor_landscape.get("amazon_seller_pct", 0),
            "estimated_monthly_sales": competitor_landscape.get("estimated_monthly_sales", 0),
        })

    # Fallback: if avg_price is still 0, compute from detailed products
    if not metrics["avg_price"] and detailed_products:
        prices = [p.get("price") for p in detailed_products if p.get("price")]
        if prices:
            metrics["avg_price"] = round(sum(prices) / len(prices), 2)
            logger.info(
                "Computed avg_price from %d detailed products: $%.2f",
                len(prices), metrics["avg_price"],
            )

    # Fallback: if avg_bsr is still 0, compute from detailed products
    if not metrics["avg_bsr"] and detailed_products:
        bsrs = [p.get("current_bsr") for p in detailed_products if p.get("current_bsr")]
        if bsrs:
            metrics["avg_bsr"] = round(sum(bsrs) / len(bsrs))

    # Fallback: if avg_review_count is still 0, compute from detailed products
    if not metrics["avg_review_count"] and detailed_products:
        reviews = [p.get("review_count") for p in detailed_products if p.get("review_count")]
        if reviews:
            metrics["avg_review_count"] = round(sum(reviews) / len(reviews))

    # Compute estimated_monthly_sales from BSR using regression model
    if not metrics["estimated_monthly_sales"] and metrics["avg_bsr"]:
        from app.core.bsr_regression import BSRSalesEstimator
        estimator = BSRSalesEstimator()
        metrics["estimated_monthly_sales"] = estimator.estimate_monthly_sales(
            bsr=int(metrics["avg_bsr"]),
            category=metrics.get("category", "default"),
        )
        logger.info(
            "Estimated monthly sales from BSR %d: %d units",
            metrics["avg_bsr"], metrics["estimated_monthly_sales"],
        )

    # Fallback: if still zero but we have products with prices, estimate from product count
    if not metrics["estimated_monthly_sales"]:
        metrics["estimated_monthly_sales"] = 300
        logger.info("Using fallback estimated_monthly_sales: 300")

    return metrics


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
        metrics["avg_cpc"] = ppc_strategy.get("avg_cpc", metrics.get("avg_cpc", 1.5))
        metrics["break_even_acos"] = ppc_strategy.get("break_even_acos", 0)
        metrics["relevant_keyword_count"] = ppc_strategy.get("keyword_count", 0)
        metrics["ppc_budget_90d"] = ppc_strategy.get("budget_90d", 0)
        metrics["estimated_acos"] = ppc_strategy.get("estimated_acos", 35)

    if review_strategy:
        metrics["review_threshold"] = review_strategy.get("review_threshold", {}).get("threshold", 50)
        metrics["weeks_to_review_threshold"] = review_strategy.get("timeline", {}).get("organic_weeks", 52)

    if supplier_data:
        margins = supplier_data.get("margins", {})
        metrics["pre_ppc_margin_pct"] = margins.get("pre_ppc_margin_pct", metrics.get("pre_ppc_margin_pct", 0))
        metrics["post_ppc_margin_pct"] = margins.get("post_ppc_margin_pct", metrics.get("post_ppc_margin_pct", 0))

        landed = supplier_data.get("landed_cost", {})
        metrics["landed_cost"] = landed.get("total_landed_cost_usd_per_unit", metrics.get("landed_cost", 0))

    # Supplier score defaults
    metrics.setdefault("supplier_count", 5)
    metrics.setdefault("best_supplier_score", 70)
    metrics.setdefault("min_moq", 500)
    metrics.setdefault("break_even_week_base", 16)
    metrics.setdefault("search_volume", 3000)
    metrics.setdefault("monthly_revenue_per_seller", 5000)


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
