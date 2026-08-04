"""Bir xil spec'li rang variantlarini guruhlash uchun testlar.

Texnomart katalogida bir xil model+RAM+xotira har rang uchun alohida mahsulot
sifatida turadi (ba'zan narxi ham farq qiladi). Natijada bitta telefon 2-4 marta
ko'rinib qolardi — shu yerdagi testlar guruhlash mantiqini qoplaydi.

Run with: python3 -m tests.test_variant_grouping (repo ildizidan)
"""
from __future__ import annotations

from core.models import Phone, QueryFilter
from core.recommender import group_variants, recommend


def _phone(color: str, price: int, **kw) -> Phone:
    base = dict(brand="Apple", model="iPhone Air", ram=12, storage=256,
                source_label="texno")
    base.update(kw)
    return Phone(color=color, price=price, **base)


def test_groups_same_spec_different_colors() -> None:
    phones = [
        _phone("Sky Blue", 14_499_000),
        _phone("Light Gold", 14_499_000),
        _phone("Cloud White", 15_299_000),
        _phone("Space Black", 15_299_000),
    ]

    grouped = group_variants(phones)

    assert len(grouped) == 1
    row = grouped[0]
    assert row.price == 14_499_000       # eng arzon variant asosiy narx
    assert row.price_to == 15_299_000    # oraliqning yuqori chegarasi
    assert row.colors == ["Sky Blue", "Light Gold", "Cloud White", "Space Black"]


def test_identical_prices_leave_no_range() -> None:
    phones = [
        _phone("Loden Green", 5_133_000, brand="Huawei", model="nova 13"),
        _phone("White", 5_133_000, brand="Huawei", model="nova 13"),
        _phone("Black", 5_133_000, brand="Huawei", model="nova 13"),
    ]

    grouped = group_variants(phones)

    assert len(grouped) == 1
    assert grouped[0].price == 5_133_000
    assert grouped[0].price_to is None   # farq yo'q -> oraliq ko'rsatilmaydi
    assert len(grouped[0].colors) == 3


def test_different_storage_stays_separate() -> None:
    phones = [
        _phone("Black", 4_199_000, storage=128),
        _phone("Black", 5_199_000, storage=256),
    ]

    assert len(group_variants(phones)) == 2


def test_different_source_stays_separate() -> None:
    phones = [
        _phone("Black", 4_199_000, source_label="texno"),
        _phone("Black", 4_050_000, source_label="baza"),
    ]

    assert len(group_variants(phones)) == 2


def test_preserves_first_seen_order() -> None:
    phones = [
        _phone("Black", 9_000_000, brand="Samsung", model="Galaxy S25"),
        _phone("Blue", 4_199_000),
        _phone("Green", 9_000_000, brand="Samsung", model="Galaxy S25"),
    ]

    grouped = group_variants(phones)

    assert [p.model for p in grouped] == ["Galaxy S25", "iPhone Air"]


def test_missing_price_variant_does_not_break_range() -> None:
    phones = [
        _phone("Black", None),
        _phone("Blue", 4_199_000),
    ]

    grouped = group_variants(phones)

    assert len(grouped) == 1
    assert grouped[0].price == 4_199_000
    assert grouped[0].price_to is None


def test_short_spec_renders_price_range_and_colors() -> None:
    grouped = group_variants([
        _phone("Sky Blue", 14_499_000),
        _phone("Cloud White", 15_299_000),
    ])

    text = grouped[0].short_spec()

    assert "14 499 000 – 15 299 000 so'm" in text
    assert "Sky Blue, Cloud White" in text


def test_short_spec_single_price_unchanged() -> None:
    text = _phone("Sky Blue", 14_499_000).short_spec()

    assert "14 499 000 so'm" in text
    assert "–" not in text


def test_recommend_limit_counts_groups_not_variants() -> None:
    phones = [
        _phone("Sky Blue", 14_499_000),
        _phone("Light Gold", 14_499_000),
        _phone("Cloud White", 15_299_000),
        _phone("Black", 4_199_000, brand="Xiaomi", model="Redmi 15C"),
        _phone("Blue", 4_199_000, brand="Xiaomi", model="Redmi 15C"),
    ]

    result, _ = recommend(phones, QueryFilter(), limit=5)

    assert len(result) == 2   # 5 ta variant emas, 2 ta model


def test_color_filter_keeps_only_matching_variant() -> None:
    phones = [
        _phone("Sky Blue", 14_499_000),
        _phone("Space Black", 15_299_000),
    ]

    result, _ = recommend(phones, QueryFilter(color="black"), limit=5)

    assert len(result) == 1
    assert result[0].colors == ["Space Black"]
    assert result[0].price == 15_299_000
    assert result[0].price_to is None


def main_test() -> None:
    test_groups_same_spec_different_colors()
    test_identical_prices_leave_no_range()
    test_different_storage_stays_separate()
    test_different_source_stays_separate()
    test_preserves_first_seen_order()
    test_missing_price_variant_does_not_break_range()
    test_short_spec_renders_price_range_and_colors()
    test_short_spec_single_price_unchanged()
    test_recommend_limit_counts_groups_not_variants()
    test_color_filter_keeps_only_matching_variant()
    print("variant grouping tests passed")


if __name__ == "__main__":
    main_test()
