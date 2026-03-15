"""Celery task definitions for Omniscient background processing."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async DB session helper — Celery workers run in sync context, so we need
# our own engine + event loop to run async DB operations.
# ---------------------------------------------------------------------------
_engine = None
_session_factory = None


def _get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazily create an async engine + session factory for Celery workers."""
    global _engine, _session_factory
    if _session_factory is None:
        settings = Settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
        )
        _session_factory = async_sessionmaker(
            bind=_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def _run_async(coro):
    """Run an async coroutine in a new event loop (safe for Celery workers)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def _get_llm_client():
    """Create an LLM client from settings."""
    from app.llm.factory import create_llm_client
    return create_llm_client(Settings())


# ═══════════════════════════════════════════════════════════════════════════
# 1. Full Niche Analysis Pipeline
# ═══════════════════════════════════════════════════════════════════════════
@celery_app.task(bind=True, name="app.workers.tasks.run_full_analysis", max_retries=2)
def run_full_analysis(self, niche_id: int, keyword: str, options: dict | None = None):
    """
    Master analysis pipeline for a niche.

    Steps:
    1. Scrape Amazon search results for the keyword
    2. Scrape top product pages (details, BSR, reviews)
    3. Run competitor analysis
    4. Fetch supplier data
    5. Build PPC strategy
    6. Build review strategy
    7. Generate financial projections
    8. Generate marketing plan
    9. Compute Omniscient Score and save recommendation
    """
    options = options or {}
    logger.info("Starting full analysis for niche %d: %s", niche_id, keyword)

    try:
        _run_async(_run_full_analysis_async(self, niche_id, keyword, options))
    except Exception as exc:
        logger.exception("Full analysis failed for niche %d", niche_id)
        _run_async(_update_niche_status(niche_id, "failed", str(exc)))
        raise self.retry(exc=exc, countdown=60 * (self.request.retries + 1))


async def _run_full_analysis_async(task, niche_id: int, keyword: str, options: dict):
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

        # ── Step 1: Scrape search results ──────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_search", "progress": 5})
        products_data = await _scrape_search_results(keyword)

        if not products_data:
            await _update_niche_status(niche_id, "failed", "No products found for keyword")
            return

        # ── Step 2: Save products and scrape details ───────────────────
        task.update_state(state="PROGRESS", meta={"step": "scraping_products", "progress": 15})
        product_ids = await _save_products(db, niche_id, products_data)

        # Scrape individual product pages for detailed data
        detailed_products = await _scrape_product_details(db, niche_id, products_data[:20])
        task.update_state(state="PROGRESS", meta={"step": "products_scraped", "progress": 30})

        # ── Step 3: Competitor analysis ────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "competitor_analysis", "progress": 35})
        from app.services.competitor_service import CompetitorService
        competitor_svc = CompetitorService(db, llm_client)

        competitor_landscape = await competitor_svc.analyze_landscape(
            niche_id=niche_id,
            keyword=keyword,
        )

        # ── Step 4: Analyze reviews (top 10 products) ──────────────────
        task.update_state(state="PROGRESS", meta={"step": "review_analysis", "progress": 45})
        from app.services.review_analyzer import ReviewAnalyzer
        review_analyzer = ReviewAnalyzer(llm_client)

        review_insights = None
        all_reviews = await _collect_reviews(db, niche_id)
        if all_reviews:
            try:
                review_insights = await review_analyzer.analyze_reviews(all_reviews)
            except Exception as e:
                logger.warning("Review analysis failed: %s", e)

        # ── Step 4b: Product Blueprint (complaint analysis) ──────────
        task.update_state(state="PROGRESS", meta={"step": "product_blueprint", "progress": 48})
        from app.services.product_blueprint import ProductBlueprintService
        blueprint_svc = ProductBlueprintService(llm_client)

        product_blueprint = None
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

        product_spec = None
        try:
            product_spec = await spec_gen.generate_product_spec(
                niche_keyword=keyword,
                competitor_data=competitor_landscape,
                review_insights=review_insights,
            )
        except Exception as e:
            logger.warning("Product spec generation failed: %s", e)

        # ── Step 6: Supplier analysis ──────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "supplier_analysis", "progress": 55})
        from app.services.supplier_service import SupplierService
        supplier_svc = SupplierService(db)

        metrics = _build_base_metrics(competitor_landscape, detailed_products)
        supplier_data = None
        try:
            supplier_data = await _analyze_suppliers(db, niche_id, metrics)
        except Exception as e:
            logger.warning("Supplier analysis failed: %s", e)

        # ── Step 7: PPC strategy ───────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "ppc_strategy", "progress": 65})
        from app.services.ppc_service import PPCService
        ppc_svc = PPCService(db, llm_client)

        ppc_strategy = None
        try:
            ppc_strategy = await ppc_svc.generate_ppc_strategy(
                niche_id=niche_id,
                niche_keyword=keyword,
                avg_price=metrics.get("avg_price", 0),
                pre_ppc_margin_pct=metrics.get("pre_ppc_margin_pct", 30),
                avg_cpc=metrics.get("avg_cpc", 1.5),
            )
        except Exception as e:
            logger.warning("PPC strategy generation failed: %s", e)

        # ── Step 8: Review strategy ────────────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "review_strategy", "progress": 72})
        from app.services.review_strategy import ReviewStrategyService
        review_svc = ReviewStrategyService(db, llm_client)

        review_strategy = None
        try:
            review_strategy = await review_svc.generate_review_strategy(
                niche_id=niche_id,
                niche_keyword=keyword,
                avg_price=metrics.get("avg_price", 0),
                estimated_monthly_sales=metrics.get("estimated_monthly_sales", 0),
            )
        except Exception as e:
            logger.warning("Review strategy generation failed: %s", e)

        # ── Step 9: Financial projections ──────────────────────────────
        task.update_state(state="PROGRESS", meta={"step": "financial_projections", "progress": 80})
        from app.services.sales_forecast import SalesForecastService
        forecast_svc = SalesForecastService(db)

        financial_summary = None
        try:
            forecast = forecast_svc.generate_forecast(
                selling_price=metrics.get("avg_price", 30),
                landed_cost=metrics.get("landed_cost", 8),
                fba_fees=metrics.get("fba_fees", 5),
                base_weekly_sales=max(1, metrics.get("estimated_monthly_sales", 100) // 4),
                initial_ppc_daily=metrics.get("ppc_daily_budget", 30),
            )
            financial_summary = forecast_svc.summarize_forecast(forecast)
            await forecast_svc.save_projections(niche_id, forecast)

            # Calculate launch capital
            launch_capital = forecast_svc.calculate_launch_capital(
                landed_cost=metrics.get("landed_cost", 8),
                initial_order_qty=metrics.get("initial_order_qty", 500),
                vine_cost=review_strategy.get("vine_plan", {}).get("costs", {}).get("total_vine_cost", 0) if review_strategy else 0,
                ppc_budget_90_days=metrics.get("ppc_budget_90d", 2700),
            )
            metrics["total_launch_capital"] = launch_capital["total_launch_capital"]
        except Exception as e:
            logger.warning("Financial projections failed: %s", e)

        # ── Step 10: Marketing plan ────────────────────────────────────
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

        # ── Step 10b: Consolidated financial report ─────────────────
        task.update_state(state="PROGRESS", meta={"step": "financial_report", "progress": 90})
        from app.services.financial_report import FinancialReportService
        fin_report_svc = FinancialReportService()

        financial_report = None
        try:
            # Estimate FOB cost from landed cost (reverse-engineer)
            fob_estimate = metrics.get("landed_cost", 8) * 0.55  # FOB is roughly 55% of landed
            product_dims = _extract_avg_dimensions(detailed_products)
            financial_report = await fin_report_svc.generate_full_report(
                selling_price=metrics.get("avg_price", 30),
                unit_cost_fob=fob_estimate,
                product_dims=product_dims,
                category=metrics.get("category", "default"),
                order_quantity=metrics.get("initial_order_qty", 500),
                estimated_monthly_sales=metrics.get("estimated_monthly_sales", 200),
                avg_cpc=metrics.get("avg_cpc", 1.50),
                launch_ppc_daily=metrics.get("ppc_daily_budget", 30),
            )
        except Exception as e:
            logger.warning("Consolidated financial report failed: %s", e)

        # ── Step 11: Compute Omniscient Score & save recommendation ────
        task.update_state(state="PROGRESS", meta={"step": "scoring", "progress": 93})
        from app.services.recommendation_engine import RecommendationEngine
        engine = RecommendationEngine(db, llm_client)

        # Enrich metrics with everything we've gathered
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
                if product.bsr_current:
                    await tracker.record_bsr(
                        product_id=product.id,
                        asin=product.asin,
                        bsr=product.bsr_current,
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
            await svc.analyze_landscape(niche_id=niche_id, keyword=keyword)
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
        return await scraper.scrape_search_results(keyword, max_pages=3)
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

        # Check if product already exists
        stmt = select(Product).where(Product.asin == asin, Product.niche_id == niche_id)
        existing = (await db.execute(stmt)).scalar_one_or_none()

        if existing:
            # Update existing
            existing.title = p.get("title", existing.title)
            existing.current_price = p.get("price", existing.current_price)
            existing.bsr_current = p.get("bsr", existing.bsr_current)
            existing.rating = p.get("rating", existing.rating)
            existing.review_count = p.get("review_count", existing.review_count)
            existing.main_image_url = p.get("image_url", existing.main_image_url)
            product_ids.append(existing.id)
        else:
            product = Product(
                niche_id=niche_id,
                asin=asin,
                title=p.get("title", ""),
                current_price=p.get("price"),
                bsr_current=p.get("bsr"),
                rating=p.get("rating"),
                review_count=p.get("review_count", 0),
                main_image_url=p.get("image_url"),
            )
            db.add(product)
            await db.flush()
            product_ids.append(product.id)

    await db.commit()
    return product_ids


async def _scrape_product_details(
    db: AsyncSession, niche_id: int, products_data: list[dict]
) -> list[dict]:
    """Scrape detailed product pages for enriched data."""
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
        except Exception as e:
            logger.warning("Failed to scrape details for %s: %s", asin, e)

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

    svc = SupplierService(db)
    avg_price = metrics.get("avg_price", 30)

    # Calculate landed cost and margins
    landed = svc.calculate_landed_cost(
        unit_price_cny=avg_price * 0.15,  # Rough estimate: 15% of sell price in CNY
        units=500,
        weight_kg_per_unit=0.5,
    )

    margin = svc.calculate_margins(
        selling_price=avg_price,
        landed_cost=landed["total_landed_cost_usd_per_unit"],
        fba_fee=metrics.get("fba_fees", 5),
        referral_fee_pct=0.15,
        avg_cpc=metrics.get("avg_cpc", 1.5),
        conversion_rate=0.12,
    )

    metrics["landed_cost"] = landed["total_landed_cost_usd_per_unit"]
    metrics["pre_ppc_margin_pct"] = margin["pre_ppc_margin_pct"]
    metrics["post_ppc_margin_pct"] = margin["post_ppc_margin_pct"]

    return {"landed_cost": landed, "margins": margin}


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
        metrics.update({
            "avg_price": competitor_landscape.get("avg_price", 0),
            "avg_bsr": competitor_landscape.get("avg_bsr", 0),
            "avg_rating": competitor_landscape.get("avg_rating", 0),
            "avg_review_count": competitor_landscape.get("avg_review_count", 0),
            "median_competitor_reviews": competitor_landscape.get("median_reviews", 0),
            "avg_listing_quality": competitor_landscape.get("avg_listing_quality", 50),
            "strong_seller_count": competitor_landscape.get("strong_seller_count", 0),
            "amazon_seller_pct": competitor_landscape.get("amazon_seller_pct", 0),
            "estimated_monthly_sales": competitor_landscape.get("estimated_monthly_sales", 0),
        })

    return metrics


def _enrich_metrics(
    metrics: dict,
    competitor_landscape: dict | None,
    ppc_strategy: dict | None,
    review_strategy: dict | None,
    supplier_data: dict | None,
):
    """Enrich the metrics dict with data from all analysis services."""
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
