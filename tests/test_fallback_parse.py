"""Regex fallback parser (Gemini yo'q/xato bo'lganda) uchun testlar.

Run with: python3 -m tests.test_fallback_parse (repo ildizidan)
"""
from __future__ import annotations

from core import ai
from core.recommender import recommend
from sources.sheets import load_phones


def test_end_to_end_a51_query_matches_only_db_record() -> None:
    """Regressiya: model filtrsiz qolib eng katta-spec telefonlar chiqib ketmasin."""
    phones = load_phones()
    f = ai._fallback_parse("menga A51 modeli haqida aytchi")
    top, relaxed = recommend(phones, f, limit=5)

    assert relaxed is False
    assert len(top) >= 1
    assert all("a51" in (p.model or "").lower() for p in top)


def test_extracts_concatenated_model_number() -> None:
    f = ai._fallback_parse("menga A51 modeli haqida aytchi")
    assert f.model == "a51"
    assert f.brand is None
    assert f.is_phone_related is True


def test_extracts_model_with_explicit_brand() -> None:
    f = ai._fallback_parse("Samsung Galaxy S24 haqida aytchi")
    assert f.brand == "Samsung"
    assert f.model == "s24"


def test_does_not_treat_spec_values_as_model() -> None:
    assert ai._fallback_parse("128gb xotirali qora Samsung").model is None
    assert ai._fallback_parse("8gb ram kerak").model is None
    assert ai._fallback_parse("5000mah batareyali telefon").model is None
    assert ai._fallback_parse("5mln atrofida telefon").model is None
    assert ai._fallback_parse("eng arzon 10 ta korsat").model is None


def test_does_not_treat_network_generation_as_model() -> None:
    assert ai._fallback_parse("5G telefon kerak").model is None
    assert ai._fallback_parse("4G qollab quvvatlaydigan telefon").model is None


def test_model_alongside_network_generation_still_detected() -> None:
    f = ai._fallback_parse("Samsung A51 5G modeli")
    assert f.model == "a51"


def test_model_word_marks_text_as_phone_related() -> None:
    assert ai.is_phone_related_text("A51 modeli haqida aytchi") is True
    assert ai.is_phone_related_text("bu qanday model?") is True


def test_tel_shorthand_and_suffixed_ram_marks_phone_related() -> None:
    assert ai.is_phone_related_text("12-20GB ramlik Tel kerak arzonidan") is True
    assert ai.is_phone_related_text("tel kerak") is True
    assert ai.is_phone_related_text("otel haqida") is False
    assert ai.is_phone_related_text("kartel") is False


def main_test() -> None:
    test_end_to_end_a51_query_matches_only_db_record()
    test_extracts_concatenated_model_number()
    test_extracts_model_with_explicit_brand()
    test_does_not_treat_spec_values_as_model()
    test_does_not_treat_network_generation_as_model()
    test_model_alongside_network_generation_still_detected()
    test_model_word_marks_text_as_phone_related()
    test_tel_shorthand_and_suffixed_ram_marks_phone_related()
    print("fallback parse tests passed")


if __name__ == "__main__":
    main_test()
