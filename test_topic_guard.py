"""Tests for phone-topic classification and off-topic blocking."""
from __future__ import annotations

import ai
import models
from topic_guard import OffTopicGuard


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


def test_second_off_topic_inside_window_blocks_for_one_hour() -> None:
    guard = OffTopicGuard()

    assert guard.register_off_topic(7, now=100.0) == "warn"
    assert guard.register_off_topic(7, now=3699.0) == "blocked"
    assert guard.is_blocked(7, now=7298.0) is True
    assert guard.is_blocked(7, now=7299.0) is False


def test_expired_first_strike_starts_new_warning() -> None:
    guard = OffTopicGuard()

    assert guard.register_off_topic(7, now=100.0) == "warn"
    assert guard.register_off_topic(7, now=3700.0) == "warn"
    assert guard.is_blocked(7, now=3700.0) is False


def main_test() -> None:
    test_phone_topic_classifier()
    test_fallback_parse_carries_topic_classification()
    test_gemini_schema_requires_topic_classification()
    test_second_off_topic_inside_window_blocks_for_one_hour()
    test_expired_first_strike_starts_new_warning()
    print("topic guard tests passed")


if __name__ == "__main__":
    main_test()
