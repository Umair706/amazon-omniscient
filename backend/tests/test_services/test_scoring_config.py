"""Resolving and validating the tunable scoring config."""

from app.services.scoring_config import (
    DEFAULT_WEIGHTS,
    SCORING_ENGINE_VERSION,
    fingerprint_effective_config,
    resolve_allow_seasonal,
    resolve_effective_config,
    resolve_sales_multiplier,
    resolve_thresholds,
    resolve_weights,
    validate_scoring_config,
)


class TestResolve:
    def test_no_config_returns_marketplace_defaults(self):
        au = resolve_thresholds("AU", None)
        assert au["price_max"] == 100
        assert au["review_moat_max"] == 500

    def test_override_replaces_only_the_named_threshold(self):
        config = {"thresholds": {"AU": {"price_max": 150}}}
        au = resolve_thresholds("AU", config)
        assert au["price_max"] == 150          # overridden
        assert au["review_moat_max"] == 500    # still the AU default

    def test_unknown_threshold_key_is_ignored(self):
        config = {"thresholds": {"AU": {"nonsense": 1}}}
        assert "nonsense" not in resolve_thresholds("AU", config)

    def test_weights_default_when_absent(self):
        assert resolve_weights(None) == DEFAULT_WEIGHTS

    def test_full_weight_override_is_used(self):
        weights = {k: (0.2 if k == "demand" else 0.1) for k in DEFAULT_WEIGHTS}
        weights["launch_feasibility"] = 0.0  # keep the sum at 1.0
        resolved = resolve_weights({"weights": weights})
        assert resolved["demand"] == 0.2

    def test_sales_multiplier_defaults_to_one(self):
        assert resolve_sales_multiplier("AU", None) == 1.0
        assert resolve_sales_multiplier("AU", {"sales_multiplier": {"US": 2.0}}) == 1.0

    def test_sales_multiplier_override(self):
        assert resolve_sales_multiplier("AU", {"sales_multiplier": {"AU": 1.5}}) == 1.5

    def test_allow_seasonal_defaults_false(self):
        assert resolve_allow_seasonal("AU", None) is False
        assert resolve_allow_seasonal("AU", {"allow_seasonal": {"AU": True}}) is True


class TestSnapshot:
    def test_effective_config_with_no_overrides_is_not_custom(self):
        eff = resolve_effective_config("AU", None)
        assert eff["is_custom"] is False
        assert eff["engine_version"] == SCORING_ENGINE_VERSION
        assert eff["marketplace"] == "AU"
        assert eff["thresholds"]["price_max"] == 100

    def test_effective_config_with_overrides_is_custom(self):
        eff = resolve_effective_config("AU", {"thresholds": {"AU": {"price_max": 150}}})
        assert eff["is_custom"] is True
        assert eff["thresholds"]["price_max"] == 150

    def test_same_rules_share_a_fingerprint(self):
        a = fingerprint_effective_config(resolve_effective_config("AU", None))
        b = fingerprint_effective_config(resolve_effective_config("AU", None))
        assert a == b

    def test_different_rules_differ_in_fingerprint(self):
        default = fingerprint_effective_config(resolve_effective_config("AU", None))
        custom = fingerprint_effective_config(
            resolve_effective_config("AU", {"thresholds": {"AU": {"price_max": 150}}})
        )
        assert default != custom


class TestValidate:
    def test_valid_config_has_no_errors(self):
        config = {
            "thresholds": {"AU": {"price_min": 25, "price_max": 120}},
            "sales_multiplier": {"AU": 1.5},
            "allow_seasonal": {"AU": True},
        }
        assert validate_scoring_config(config) == []

    def test_price_min_above_max_is_rejected(self):
        errors = validate_scoring_config({"thresholds": {"AU": {"price_min": 90, "price_max": 30}}})
        assert any("price_min must be below price_max" in e for e in errors)

    def test_out_of_range_threshold_is_rejected(self):
        errors = validate_scoring_config({"thresholds": {"US": {"margin_min": 250}}})
        assert any("margin_min" in e for e in errors)

    def test_weights_must_sum_to_one(self):
        weights = {k: 0.5 for k in DEFAULT_WEIGHTS}  # sums to 4.5
        errors = validate_scoring_config({"weights": weights})
        assert any("sum to 1.0" in e for e in errors)

    def test_incomplete_weights_are_rejected(self):
        errors = validate_scoring_config({"weights": {"demand": 1.0}})
        assert any("missing" in e for e in errors)

    def test_negative_sales_multiplier_is_rejected(self):
        errors = validate_scoring_config({"sales_multiplier": {"AU": -1}})
        assert any("sales_multiplier.AU" in e for e in errors)
