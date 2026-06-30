"""Tests for phone-topic classification and off-topic blocking."""
from __future__ import annotations

import ai
import models


def test_phone_topic_classifier() -> None:
    related = [
        "5 mln gacha Samsung telefon kerak",
        "kamera yaxshi smartfon tavsiya qil",
        "iPhone 15 Pro bilan Pixel 9 ni solishtir",
        "bolshoy batareyali telefon",
        "best Android phone under 500 dollars",
    ]
    unrelated = [
        "insonlar ongi haqida nimalarni bilasan?",
        "menga ertak aytib ber",
        "bugun ob-havo qanday?",
        "2 + 2 nechchi?",
    ]

    assert all(ai.is_phone_related_text(text) for text in related)
    assert not any(ai.is_phone_related_text(text) for text in unrelated)


def test_fallback_parse_carries_topic_classification() -> None:
    assert ai._fallback_parse("Samsung telefon kerak").is_phone_related is True
    assert ai._fallback_parse("insonlar ongi haqida nimalarni bilasan?").is_phone_related is False


def test_gemini_schema_requires_topic_classification() -> None:
    assert models.QUERY_FILTER_SCHEMA["properties"]["is_phone_related"]["type"] == "boolean"
    assert "is_phone_related" in models.QUERY_FILTER_SCHEMA["required"]


def main_test() -> None:
    test_phone_topic_classifier()
    test_fallback_parse_carries_topic_classification()
    test_gemini_schema_requires_topic_classification()
    print("topic guard tests passed")


if __name__ == "__main__":
    main_test()
