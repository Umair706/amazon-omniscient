"""Scoring service — Omniscient Score (0-100) with 9 weighted sub-scores and hard disqualification filters."""

import logging

logger = logging.getLogger(__name__)


class ScoringService:
    """
    Computes the Omniscient Score (0-100) for a niche/product opportunity.

    Supports marketplace-specific thresholds. AU market has lower volume
    thresholds since it's ~8% of US market size.

    9 weighted sub-scores:
    1. Demand Score (15%) — BSR, search volume, sales velocity
    2. Competition Score (15%) — listing quality, review moat, seller count
    3. Revenue Score (10%) — price point, monthly revenue per seller
    4. Margin Score (15%) — landed cost, FBA fees, post-PPC margin
    5. Trend Score (10%) — BSR trend, search volume trend, seasonality
    6. Review Feasibility (10%) — review threshold, weeks to compete
    7. Supplier Score (10%) — availability, MOQ, lead time, cost
    8. PPC Viability (10%) — CPC, break-even ACOS, competition density
    9. Launch Feasibility (5%) — capital required, time to break-even

    9 hard disqualification filters (marketplace-adjusted):
    - Avg selling price outside target range
    - Review moat threshold
    - BSR threshold (demand)
    - Pre-PPC margin minimum
    - Market dominated by Amazon
    - Hazmat/restricted category
    - IP/patent risk indicators
    - Seasonal-only demand (unless allowed)
    - Review velocity trap
    """

    # Sub-score weights
    WEIGHTS = {
        "demand": 0.15,
        "competition": 0.15,
        "revenue": 0.10,
        "margin": 0.15,
        "trend": 0.10,
        "review_feasibility": 0.10,
        "supplier": 0.10,
        "ppc_viability": 0.10,
        "launch_feasibility": 0.05,
    }

    # Marketplace-specific hard filter thresholds
    # AU has: wider price range (AUD), lower review moat (smaller market),
    # higher BSR threshold (fewer sellers), same margin requirement
    MARKETPLACE_THRESHOLDS = {
        "US": {
            "price_min": 15,
            "price_max": 70,
            "review_moat_max": 2000,
            "bsr_max": 50000,
            "margin_min": 25,
            "amazon_dominance_max": 30,
            "review_velocity_max": 5.0,
        },
        "AU": {
            "price_min": 20,   # AUD — slightly higher floor due to currency
            "price_max": 100,  # AUD — higher ceiling
            "review_moat_max": 500,  # AU has far fewer reviews per product
            "bsr_max": 20000,  # AU catalog is smaller, BSR ranks are lower
            "margin_min": 25,  # Same margin requirement
            "amazon_dominance_max": 30,
            "review_velocity_max": 3.0,  # Tighter in smaller market
        },
    }

    def compute_score(self, metrics: dict) -> dict:
        """
        Compute the Omniscient Score from raw metrics.

        Parameters
        ----------
        metrics : dict
            All raw metrics needed for scoring. Expected keys described
            in each sub-score method.

        Returns
        -------
        dict
            omniscient_score, confidence_tier, sub_scores, hard_filters,
            pass_all_filters, fail_reasons
        """
        # Compute sub-scores
        sub_scores = {
            "demand": self._score_demand(metrics),
            "competition": self._score_competition(metrics),
            "revenue": self._score_revenue(metrics),
            "margin": self._score_margin(metrics),
            "trend": self._score_trend(metrics),
            "review_feasibility": self._score_review_feasibility(metrics),
            "supplier": self._score_supplier(metrics),
            "ppc_viability": self._score_ppc_viability(metrics),
            "launch_feasibility": self._score_launch_feasibility(metrics),
        }

        # Weighted total
        omniscient_score = sum(
            sub_scores[k] * self.WEIGHTS[k] for k in self.WEIGHTS
        )
        omniscient_score = round(min(100, max(0, omniscient_score)), 1)

        # Hard filters
        filter_results = self._apply_hard_filters(metrics)
        pass_all = all(f["passed"] for f in filter_results)
        fail_reasons = [f["reason"] for f in filter_results if not f["passed"]]

        # Confidence tier
        if not pass_all:
            tier = "FAIL"
        elif omniscient_score >= 80:
            tier = "HIGH"
        elif omniscient_score >= 60:
            tier = "MEDIUM"
        elif omniscient_score >= 40:
            tier = "LOW"
        else:
            tier = "VERY_LOW"

        return {
            "omniscient_score": omniscient_score,
            "confidence_tier": tier,
            "sub_scores": sub_scores,
            "hard_filters": filter_results,
            "pass_all_filters": pass_all,
            "fail_reasons": fail_reasons,
        }

    # ------------------------------------------------------------------
    # Sub-score calculators (each returns 0-100)
    # ------------------------------------------------------------------

    @staticmethod
    def _score_demand(m: dict) -> float:
        """Search volume, BSR, estimated monthly sales.

        Thresholds scale by marketplace. AU search volumes and sales
        are ~8% of US, so thresholds are proportionally lower.
        """
        score = 0
        sv = m.get("search_volume", 0)
        bsr = m.get("avg_bsr", 99999)
        monthly_sales = m.get("estimated_monthly_sales", 0)
        marketplace = m.get("marketplace", "US")

        # Market scale factor for demand thresholds
        scale = 0.08 if marketplace == "AU" else 1.0

        # Search volume (40 pts) — scaled by market size
        sv_tiers = [
            (10000 * scale, 40),
            (5000 * scale, 32),
            (2000 * scale, 24),
            (1000 * scale, 16),
            (500 * scale, 8),
        ]
        sv_score = 2
        for threshold, pts in sv_tiers:
            if sv >= threshold:
                sv_score = pts
                break
        score += sv_score

        # BSR (30 pts — lower is better)
        # AU has smaller catalog so BSR thresholds are proportionally lower
        bsr_scale = 0.4 if marketplace == "AU" else 1.0  # AU BSR ranks tend to top out lower
        bsr_tiers = [
            (1000 * bsr_scale, 30),
            (5000 * bsr_scale, 25),
            (10000 * bsr_scale, 20),
            (25000 * bsr_scale, 14),
            (50000 * bsr_scale, 8),
        ]
        bsr_score = 2
        for threshold, pts in bsr_tiers:
            if bsr <= threshold:
                bsr_score = pts
                break
        score += bsr_score

        # Monthly sales (30 pts) — scaled by market size
        sales_tiers = [
            (1000 * scale, 30),
            (500 * scale, 24),
            (300 * scale, 18),
            (100 * scale, 12),
            (50 * scale, 6),
        ]
        sales_score = 2
        for threshold, pts in sales_tiers:
            if monthly_sales >= threshold:
                sales_score = pts
                break
        score += sales_score

        return min(100, score)

    @staticmethod
    def _score_competition(m: dict) -> float:
        """Listing quality, review moat, number of strong sellers."""
        score = 100  # Start high, deduct for strong competition
        marketplace = m.get("marketplace", "US")

        avg_listing_quality = m.get("avg_listing_quality", 50)
        median_reviews = m.get("median_competitor_reviews", 0)
        strong_sellers = m.get("strong_seller_count", 0)

        # Listing quality (deduct if competition is polished)
        if avg_listing_quality >= 80:
            score -= 30
        elif avg_listing_quality >= 60:
            score -= 15
        elif avg_listing_quality >= 40:
            score -= 5

        # Review moat (deduct for high review counts)
        # AU market has far fewer reviews, so thresholds are lower
        review_scale = 0.25 if marketplace == "AU" else 1.0
        if median_reviews >= 2000 * review_scale:
            score -= 40
        elif median_reviews >= 1000 * review_scale:
            score -= 30
        elif median_reviews >= 500 * review_scale:
            score -= 20
        elif median_reviews >= 200 * review_scale:
            score -= 10
        elif median_reviews >= 50 * review_scale:
            score -= 5

        # Strong sellers (Amazon, big brands)
        if strong_sellers >= 5:
            score -= 25
        elif strong_sellers >= 3:
            score -= 15
        elif strong_sellers >= 1:
            score -= 5

        return max(0, score)

    @staticmethod
    def _score_revenue(m: dict) -> float:
        """Price point and revenue per seller."""
        score = 0
        avg_price = m.get("avg_price", 0)
        monthly_revenue_per_seller = m.get("monthly_revenue_per_seller", 0)

        # Price sweet spot ($20-$50 is ideal for FBA)
        if 25 <= avg_price <= 45:
            score += 50
        elif 20 <= avg_price <= 50:
            score += 40
        elif 15 <= avg_price <= 70:
            score += 25
        else:
            score += 5

        # Revenue per seller
        if monthly_revenue_per_seller >= 10000:
            score += 50
        elif monthly_revenue_per_seller >= 5000:
            score += 40
        elif monthly_revenue_per_seller >= 3000:
            score += 30
        elif monthly_revenue_per_seller >= 1000:
            score += 20
        else:
            score += 5

        return min(100, score)

    @staticmethod
    def _score_margin(m: dict) -> float:
        """Pre-PPC margin, post-PPC margin."""
        score = 0
        pre_ppc = m.get("pre_ppc_margin_pct", 0)
        post_ppc = m.get("post_ppc_margin_pct", 0)

        # Pre-PPC margin (60 pts)
        if pre_ppc >= 50:
            score += 60
        elif pre_ppc >= 40:
            score += 48
        elif pre_ppc >= 35:
            score += 38
        elif pre_ppc >= 30:
            score += 28
        elif pre_ppc >= 25:
            score += 18
        else:
            score += 5

        # Post-PPC margin (40 pts)
        if post_ppc >= 25:
            score += 40
        elif post_ppc >= 20:
            score += 32
        elif post_ppc >= 15:
            score += 24
        elif post_ppc >= 10:
            score += 16
        elif post_ppc >= 5:
            score += 8
        else:
            score += 2

        return min(100, score)

    @staticmethod
    def _score_trend(m: dict) -> float:
        """BSR trend, search volume trend, seasonality."""
        score = 50  # Neutral baseline

        bsr_velocity = m.get("bsr_velocity_pct", 0)
        sv_trend = m.get("search_volume_trend", "stable")
        is_seasonal = m.get("is_seasonal", False)

        # BSR velocity (negative = improving = good)
        if bsr_velocity < -20:
            score += 25
        elif bsr_velocity < -5:
            score += 15
        elif bsr_velocity > 20:
            score -= 20
        elif bsr_velocity > 5:
            score -= 10

        # Search volume trend
        if sv_trend in ("rising", "up"):
            score += 20
        elif sv_trend in ("declining", "down"):
            score -= 20
        elif sv_trend == "stable":
            score += 5

        # Seasonality penalty
        if is_seasonal:
            score -= 15

        return max(0, min(100, score))

    @staticmethod
    def _score_review_feasibility(m: dict) -> float:
        """How feasible is it to reach competitive review counts."""
        score = 0
        review_threshold = m.get("review_threshold", 100)
        weeks_to_threshold = m.get("weeks_to_review_threshold", 52)

        # Lower threshold = easier
        if review_threshold <= 15:
            score += 50
        elif review_threshold <= 30:
            score += 40
        elif review_threshold <= 100:
            score += 25
        elif review_threshold <= 300:
            score += 15
        else:
            score += 5

        # Faster timeline = better
        if weeks_to_threshold and weeks_to_threshold <= 8:
            score += 50
        elif weeks_to_threshold and weeks_to_threshold <= 16:
            score += 40
        elif weeks_to_threshold and weeks_to_threshold <= 26:
            score += 30
        elif weeks_to_threshold and weeks_to_threshold <= 40:
            score += 20
        else:
            score += 5

        return min(100, score)

    @staticmethod
    def _score_supplier(m: dict) -> float:
        """Supplier availability and costs."""
        score = 0
        supplier_count = m.get("supplier_count", 0)
        best_supplier_score = m.get("best_supplier_score", 0)
        moq = m.get("min_moq", 9999)

        # Supplier availability (40 pts)
        if supplier_count >= 10:
            score += 40
        elif supplier_count >= 5:
            score += 30
        elif supplier_count >= 3:
            score += 20
        elif supplier_count >= 1:
            score += 10
        else:
            score += 0

        # Best supplier quality (30 pts)
        score += min(30, best_supplier_score * 0.3)

        # MOQ (30 pts — lower is better for initial testing)
        if moq <= 100:
            score += 30
        elif moq <= 300:
            score += 22
        elif moq <= 500:
            score += 15
        elif moq <= 1000:
            score += 8
        else:
            score += 2

        return min(100, score)

    @staticmethod
    def _score_ppc_viability(m: dict) -> float:
        """PPC cost-effectiveness."""
        score = 0
        avg_cpc = m.get("avg_cpc", 5.0)
        break_even_acos = m.get("break_even_acos", 0)
        keyword_count = m.get("relevant_keyword_count", 0)

        # CPC (40 pts — lower is better)
        if avg_cpc <= 0.50:
            score += 40
        elif avg_cpc <= 1.00:
            score += 32
        elif avg_cpc <= 1.50:
            score += 24
        elif avg_cpc <= 2.50:
            score += 16
        elif avg_cpc <= 4.00:
            score += 8
        else:
            score += 2

        # Break-even ACOS headroom (30 pts)
        if break_even_acos >= 50:
            score += 30
        elif break_even_acos >= 35:
            score += 24
        elif break_even_acos >= 25:
            score += 18
        elif break_even_acos >= 15:
            score += 10
        else:
            score += 2

        # Keyword diversity (30 pts)
        if keyword_count >= 50:
            score += 30
        elif keyword_count >= 30:
            score += 22
        elif keyword_count >= 15:
            score += 15
        elif keyword_count >= 5:
            score += 8
        else:
            score += 2

        return min(100, score)

    @staticmethod
    def _score_launch_feasibility(m: dict) -> float:
        """Capital requirements and time to break-even."""
        score = 0
        launch_capital = m.get("total_launch_capital", 99999)
        break_even_week = m.get("break_even_week_base", 52)

        # Capital needed (50 pts)
        if launch_capital <= 3000:
            score += 50
        elif launch_capital <= 5000:
            score += 40
        elif launch_capital <= 10000:
            score += 30
        elif launch_capital <= 20000:
            score += 20
        elif launch_capital <= 50000:
            score += 10
        else:
            score += 2

        # Time to break-even (50 pts)
        if break_even_week and break_even_week <= 8:
            score += 50
        elif break_even_week and break_even_week <= 16:
            score += 40
        elif break_even_week and break_even_week <= 26:
            score += 28
        elif break_even_week and break_even_week <= 40:
            score += 16
        else:
            score += 5

        return min(100, score)

    # ------------------------------------------------------------------
    # Hard disqualification filters
    # ------------------------------------------------------------------
    def _apply_hard_filters(self, m: dict) -> list[dict]:
        """Apply 9 hard filters. Each returns pass/fail with reason.

        Thresholds are marketplace-aware — AU market has adjusted values
        (lower review moat, different price range in AUD, adjusted BSR).
        """
        allow_seasonal = m.get("allow_seasonal", False)
        marketplace = m.get("marketplace", "US")
        thresholds = self.MARKETPLACE_THRESHOLDS.get(
            marketplace, self.MARKETPLACE_THRESHOLDS["US"]
        )
        filters = []

        # Determine currency symbol for display
        currency_sym = "A$" if marketplace == "AU" else "$"

        # 1. Price range
        avg_price = m.get("avg_price", 0)
        price_min = thresholds["price_min"]
        price_max = thresholds["price_max"]
        filters.append({
            "filter": "price_range",
            "passed": price_min <= avg_price <= price_max,
            "reason": f"Avg price {currency_sym}{avg_price:.2f} outside {currency_sym}{price_min}-{currency_sym}{price_max} range",
            "value": avg_price,
        })

        # 2. Review moat
        median_reviews = m.get("median_competitor_reviews", 0)
        review_max = thresholds["review_moat_max"]
        filters.append({
            "filter": "review_moat",
            "passed": median_reviews <= review_max,
            "reason": f"Median competitor reviews ({median_reviews}) exceeds {review_max}",
            "value": median_reviews,
        })

        # 3. BSR (demand)
        avg_bsr = m.get("avg_bsr", 99999)
        bsr_max = thresholds["bsr_max"]
        filters.append({
            "filter": "bsr_demand",
            "passed": avg_bsr <= bsr_max,
            "reason": f"Avg BSR ({avg_bsr}) exceeds {bsr_max} (low demand)",
            "value": avg_bsr,
        })

        # 4. Margin
        pre_ppc_margin = m.get("pre_ppc_margin_pct", 0)
        margin_min = thresholds["margin_min"]
        filters.append({
            "filter": "minimum_margin",
            "passed": pre_ppc_margin >= margin_min,
            "reason": f"Pre-PPC margin ({pre_ppc_margin:.1f}%) below {margin_min}% minimum",
            "value": pre_ppc_margin,
        })

        # 5. Amazon dominance
        amazon_pct = m.get("amazon_seller_pct", 0)
        dominance_max = thresholds["amazon_dominance_max"]
        filters.append({
            "filter": "amazon_dominance",
            "passed": amazon_pct <= dominance_max,
            "reason": f"Amazon sells {amazon_pct:.0f}% of top listings (>{dominance_max}% threshold)",
            "value": amazon_pct,
        })

        # 6. Hazmat/restricted
        is_restricted = m.get("is_restricted_category", False)
        filters.append({
            "filter": "restricted_category",
            "passed": not is_restricted,
            "reason": "Category is restricted/hazmat",
            "value": is_restricted,
        })

        # 7. IP/patent risk
        ip_risk = m.get("ip_risk_detected", False)
        filters.append({
            "filter": "ip_patent_risk",
            "passed": not ip_risk,
            "reason": "IP/patent risk indicators detected",
            "value": ip_risk,
        })

        # 8. Seasonality
        is_seasonal = m.get("is_seasonal", False)
        filters.append({
            "filter": "seasonality",
            "passed": not is_seasonal or allow_seasonal,
            "reason": "Seasonal-only demand detected (and allow_seasonal is off)",
            "value": is_seasonal,
        })

        # 9. Review velocity trap
        avg_review_velocity_gap = m.get("avg_review_velocity_gap_ratio", None)
        velocity_max = thresholds["review_velocity_max"]
        if avg_review_velocity_gap is not None:
            is_trap = avg_review_velocity_gap > velocity_max
            filters.append({
                "filter": "review_velocity_trap",
                "passed": not is_trap,
                "reason": (
                    f"Review velocity gap ratio ({avg_review_velocity_gap:.1f}%) "
                    f"exceeds {velocity_max}% — likely grey-hat review tactics"
                ),
                "value": avg_review_velocity_gap,
            })

        return filters
