"""Tests for the SupplierService."""

import pytest
from app.services.supplier_service import SupplierService, LandedCost


@pytest.fixture
def supplier_svc():
    """SupplierService with no LLM client (pure calculation tests)."""
    return SupplierService(llm_client=None)


class TestLandedCost:
    def test_basic_landed_cost(self, supplier_svc):
        result = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=0.5,
        )
        assert isinstance(result, LandedCost)
        assert result.total_cost_to_amazon > 0
        assert result.unit_cost == 5.0

    def test_heavier_items_cost_more(self, supplier_svc):
        light = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=0.2,
        )
        heavy = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=2.0,
        )
        assert heavy.total_cost_to_amazon > light.total_cost_to_amazon

    def test_landed_cost_includes_all_components(self, supplier_svc):
        result = supplier_svc.calculate_landed_cost(
            unit_cost=10.0, quantity=300, weight_kg=0.5,
        )
        # Total landed cost should include unit cost + shipping + duties + tariff + insurance + inspection + forwarding
        assert result.total_landed_cost >= result.unit_cost
        assert result.total_cost_to_amazon >= result.total_landed_cost

    def test_china_origin_includes_section_301(self, supplier_svc):
        result = supplier_svc.calculate_landed_cost(
            unit_cost=10.0, quantity=500, weight_kg=0.5,
            origin_country="CN",
        )
        assert result.section_301_tariff > 0
        assert result.section_301_rate > 0

    def test_non_china_origin_no_section_301(self, supplier_svc):
        result = supplier_svc.calculate_landed_cost(
            unit_cost=10.0, quantity=500, weight_kg=0.5,
            origin_country="VN",
        )
        assert result.section_301_tariff == 0
        assert result.section_301_rate == 0

    def test_air_shipping_more_expensive(self, supplier_svc):
        sea = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=0.5,
            shipping_method="sea_fcl_20ft",
        )
        air = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=0.5,
            shipping_method="air_express",
        )
        assert air.shipping_per_unit > sea.shipping_per_unit

    def test_category_duty_rates(self, supplier_svc):
        electronics = supplier_svc.calculate_landed_cost(
            unit_cost=10.0, quantity=500, weight_kg=0.5,
            category="electronics",
        )
        clothing = supplier_svc.calculate_landed_cost(
            unit_cost=10.0, quantity=500, weight_kg=0.5,
            category="clothing",
        )
        # Clothing has a higher duty rate than electronics (0% for electronics)
        assert clothing.customs_duty > electronics.customs_duty


class TestMargins:
    def test_basic_margin_calc(self, supplier_svc):
        landed = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=0.5,
        )
        result = supplier_svc.calculate_margins(
            selling_price=30, landed_cost=landed,
        )
        assert "pre_ppc_margin_pct" in result
        assert "post_ppc_margin_pct" in result
        assert result["pre_ppc_margin_pct"] > result["post_ppc_margin_pct"]

    def test_high_margin_product(self, supplier_svc):
        landed = supplier_svc.calculate_landed_cost(
            unit_cost=3.0, quantity=500, weight_kg=0.3,
        )
        result = supplier_svc.calculate_margins(
            selling_price=50, landed_cost=landed,
            ppc_cost_per_unit=1.0,
        )
        assert result["pre_ppc_margin_pct"] > 40
        assert result["meets_30pct_target"] is True

    def test_low_margin_product(self, supplier_svc):
        landed = supplier_svc.calculate_landed_cost(
            unit_cost=10.0, quantity=500, weight_kg=1.0,
        )
        result = supplier_svc.calculate_margins(
            selling_price=16, landed_cost=landed,
            ppc_cost_per_unit=3.0,
        )
        assert result["pre_ppc_margin_pct"] < 30

    def test_margin_result_contains_all_fields(self, supplier_svc):
        landed = supplier_svc.calculate_landed_cost(
            unit_cost=5.0, quantity=500, weight_kg=0.5,
        )
        result = supplier_svc.calculate_margins(
            selling_price=30, landed_cost=landed,
        )
        expected_keys = [
            "selling_price", "landed_cost", "referral_fee",
            "fba_fulfillment_fee", "monthly_storage", "returns_cost",
            "total_amazon_fees", "ppc_cost_per_unit",
            "pre_ppc_profit", "pre_ppc_margin_pct",
            "post_ppc_profit", "post_ppc_margin_pct",
            "break_even_price", "roi_pct",
            "is_profitable", "meets_30pct_target",
        ]
        for key in expected_keys:
            assert key in result, f"Missing key: {key}"


class TestSupplierScoring:
    def test_score_range(self, supplier_svc):
        result = supplier_svc.score_supplier(
            years_in_business=8, transaction_count=500,
            response_rate=0.95, on_time_delivery_rate=0.98,
            rating=4.8, has_trade_assurance=True,
            is_verified=True,
        )
        assert 0 <= result["total_score"] <= 100

    def test_excellent_supplier_high_score(self, supplier_svc):
        result = supplier_svc.score_supplier(
            years_in_business=15, transaction_count=2000,
            response_rate=0.99, on_time_delivery_rate=0.99,
            rating=5.0, has_trade_assurance=True,
            is_verified=True, is_gold_supplier=True,
            sample_available=True,
        )
        assert result["total_score"] >= 80
        assert result["tier"] == "excellent"

    def test_poor_supplier_low_score(self, supplier_svc):
        result = supplier_svc.score_supplier(
            years_in_business=1, transaction_count=5,
            response_rate=0.40, on_time_delivery_rate=0.30,
            rating=2.0, has_trade_assurance=False,
            is_verified=False,
        )
        assert result["total_score"] <= 40
        assert result["tier"] in ("risky", "fair")

    def test_score_includes_breakdown(self, supplier_svc):
        result = supplier_svc.score_supplier(
            years_in_business=5, transaction_count=100,
            response_rate=0.80, on_time_delivery_rate=0.90,
            rating=4.0,
        )
        assert "breakdown" in result
        assert "years_in_business" in result["breakdown"]
        assert "transaction_history" in result["breakdown"]
        assert "response_rate" in result["breakdown"]
        assert "on_time_delivery" in result["breakdown"]

    def test_trade_assurance_adds_points(self, supplier_svc):
        without_ta = supplier_svc.score_supplier(
            years_in_business=5, transaction_count=100,
            has_trade_assurance=False,
        )
        with_ta = supplier_svc.score_supplier(
            years_in_business=5, transaction_count=100,
            has_trade_assurance=True,
        )
        assert with_ta["total_score"] > without_ta["total_score"]
        assert with_ta["breakdown"]["trade_assurance"] == 10
        assert without_ta["breakdown"]["trade_assurance"] == 0

    def test_tier_classification(self, supplier_svc):
        # Excellent tier (>= 80)
        excellent = supplier_svc.score_supplier(
            years_in_business=8, transaction_count=1000,
            response_rate=0.95, on_time_delivery_rate=0.95,
            rating=5.0, has_trade_assurance=True,
            is_verified=True, is_gold_supplier=True,
            sample_available=True,
        )
        assert excellent["tier"] == "excellent"

        # Risky tier (< 40)
        risky = supplier_svc.score_supplier(
            years_in_business=0, transaction_count=0,
            response_rate=0.0, on_time_delivery_rate=0.0,
            rating=0.0,
        )
        assert risky["tier"] == "risky"


class TestOptimalMOQ:
    def test_basic_moq_calculation(self, supplier_svc):
        price_tiers = [
            {"min_qty": 100, "max_qty": 499, "unit_price": 5.00},
            {"min_qty": 500, "max_qty": 999, "unit_price": 4.00},
            {"min_qty": 1000, "max_qty": 9999, "unit_price": 3.50},
        ]
        result = supplier_svc.calculate_optimal_moq(
            price_tiers=price_tiers,
            estimated_monthly_sales=200,
            max_budget=10000,
        )
        assert "recommended_quantity" in result
        assert "recommended_option" in result
        assert "all_options" in result
        assert result["recommended_quantity"] > 0

    def test_budget_constraint(self, supplier_svc):
        price_tiers = [
            {"min_qty": 100, "max_qty": 499, "unit_price": 5.00},
            {"min_qty": 500, "max_qty": 999, "unit_price": 4.00},
        ]
        result = supplier_svc.calculate_optimal_moq(
            price_tiers=price_tiers,
            estimated_monthly_sales=200,
            max_budget=800,
        )
        # All options must be within budget
        for option in result["all_options"]:
            assert option["within_budget"] is True
