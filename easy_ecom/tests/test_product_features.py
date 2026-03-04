import json

from easy_ecom.domain.services.product_features import parse_features_text


def test_parse_features_from_comma_separated_text() -> None:
    parsed = json.loads(parse_features_text("Fast, Compact, Energy efficient"))
    assert parsed == {"features": ["Fast", "Compact", "Energy efficient"]}


def test_parse_features_from_bullets_and_numbers() -> None:
    raw = """
    - Long battery life
    * Waterproof
    1. Bluetooth 5.3
    """
    parsed = json.loads(parse_features_text(raw))
    assert parsed == {
        "features": ["Long battery life", "Waterproof", "Bluetooth 5.3"],
    }


def test_parse_features_empty_input_returns_empty_object() -> None:
    assert parse_features_text("   \n") == "{}"
