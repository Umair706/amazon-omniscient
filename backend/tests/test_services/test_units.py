import pytest

from app.core.units import parse_weight_lb


@pytest.mark.parametrize("text, expected_lb", [
    ("1.2 pounds", 1.2),
    ("2 lbs", 2.0),
    ("1 lb", 1.0),
    ("12 ounces", 0.75),
    ("8 oz", 0.5),
    ("0.5 kg", 1.1023),
    ("0.5 Kilograms", 1.1023),
    ("450 g", 0.9921),
    ("1,200 grams", 2.6455),
    ("1.5", 1.5),
    (3, 3.0),
])
def test_parse_weight_lb_converts_each_unit_to_pounds(text, expected_lb):
    assert parse_weight_lb(text) == pytest.approx(expected_lb, abs=1e-3)


@pytest.mark.parametrize("garbage", [None, "", "heavy", "10 x 6 cm", "N/A"])
def test_parse_weight_lb_returns_none_for_text_that_is_not_a_weight(garbage):
    assert parse_weight_lb(garbage) is None
