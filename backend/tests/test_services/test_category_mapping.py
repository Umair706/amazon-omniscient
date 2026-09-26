from app.core.category_mapping import category_slugs


def test_known_category():
    assert category_slugs("Home & Kitchen") == ("home", "home")
    assert category_slugs("Sports & Outdoors") == ("sports", "sports_and_outdoors")


def test_unknown_category_falls_back_to_default():
    assert category_slugs("Musical Instruments") == ("default", "default")
    assert category_slugs(None) == ("default", "default")
