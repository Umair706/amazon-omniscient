"""Scoring service — Omniscient Score (0-100) with 9 weighted sub-scores and hard disqualification filters."""

import logging

logger = logging.getLogger(__name__)


class ScoringService:
    """
    Computes the Omniscient Score (0-100) for a niche/product opportunity.

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

    9 hard disqualification filters:
    - Avg selling price < $15 or > $70
    - Review moat > 2000 (median competitor reviews)
    - BSR > 50000 (too low demand)
    - Pre-PPC margin < 25%
    - Market dominated by Amazon (>30% of top 10)
    - Hazmat/restricted category
    - IP/patent risk indicators
    - Seasonal-only demand (unless allowed)
    - Review velocity trap (>5 reviews per 100 sales — likely grey-hat)
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
        """Search volume, BSR, estimated monthly sales."""
        score = 0
        sv = m.get("search_volume", 0)
        bsr = m.get("avg_bsr", 99999)
        monthly_sales = m.get("estimated_monthly_sales", 0)

        # Search volume (40 pts)
        if sv >= 10000:
            score += 40
        elif sv >= 5000:
            score += 32
        elif sv >= 2000:
            score += 24
        elif sv >= 1000:
            score += 16
        elif sv >= 500:
            score += 8
        else:
            score += 2

        # BSR (30 pts — lower is better)
        if bsr <= 1000:
            score += 30
        elif bsr <= 5000:
            score += 25
        elif bsr <= 10000:
            score += 20
        elif bsr <= 25000:
            score += 14
        elif bsr <= 50000:
            score += 8
        else:
            score += 2

        # Monthly sales (30 pts)
        if monthly_sales >= 1000:
            score += 30
        elif monthly_sales >= 500:
            score += 24
        elif monthly_sales >= 300:
            score += 18
        elif monthly_sales >= 100:
            score += 12
        elif monthly_sales >= 50:
            score += 6
        else:
            score += 2

        return min(100, score)

    @staticmethod
    def _score_competition(m: dict) -> float:
        """Listing quality, review moat, number of strong sellers."""
        score = 100  # Start high, deduct for strong competition

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
        if median_reviews >= 2000:
            score -= 40
        elif median_reviews >= 1000:
            score -= 30
        elif median_reviews >= 500:
            score -= 20
        elif median_reviews >= 200:
            score -= 10
        elif median_reviews >= 50:
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
        """Apply 9 hard filters. Each returns pass/fail with reason."""
        allow_seasonal = m.get("allow_seasonal", False)
        filters = []

        # 1. Price range
        avg_price = m.get("avg_price", 0)
        filters.append({
            "filter": "price_range",
            "passed": 15 <= avg_price <= 70,
            "reason": f"Avg price ${avg_price:.2f} outside $15-$70 range",
            "value": avg_price,
        })

        # 2. Review moat
        median_reviews = m.get("median_competitor_reviews", 0)
        filters.append({
            "filter": "review_moat",
            "passed": median_reviews <= 2000,
            "reason": f"Median competitor reviews ({median_reviews}) exceeds 2000",
            "value": median_reviews,
        })

        # 3. BSR (demand)
        avg_bsr = m.get("avg_bsr", 99999)
        filters.append({
            "filter": "bsr_demand",
            "passed": avg_bsr <= 50000,
            "reason": f"Avg BSR ({avg_bsr}) exceeds 50000 (low demand)",
            "value": avg_bsr,
        })

        # 4. Margin
        pre_ppc_margin = m.get("pre_ppc_margin_pct", 0)
        filters.append({
            "filter": "minimum_margin",
            "passed": pre_ppc_margin >= 25,
            "reason": f"Pre-PPC margin ({pre_ppc_margin:.1f}%) below 25% minimum",
            "value": pre_ppc_margin,
        })

        # 5. Amazon dominance
        amazon_pct = m.get("amazon_seller_pct", 0)
        filters.append({
            "filter": "amazon_dominance",
            "passed": amazon_pct <= 30,
            "reason": f"Amazon sells {amazon_pct:.0f}% of top listings (>30% threshold)",
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
        # A niche where competitors gain >5 reviews per 100 sales/month
        # suggests grey-hat review tactics or heavy Vine manipulation,
        # making it very hard for organic entrants to compete on reviews.
        avg_review_velocity_gap = m.get("avg_review_velocity_gap_ratio", None)
        if avg_review_velocity_gap is not None:
            is_trap = avg_review_velocity_gap > 5.0
            filters.append({
                "filter": "review_velocity_trap",
                "passed": not is_trap,
                "reason": (
                    f"Review velocity gap ratio ({avg_review_velocity_gap:.1f}%) "
                    f"exceeds 5% — likely grey-hat review tactics"
                ),
                "value": avg_review_velocity_gap,
            })

        return filters
