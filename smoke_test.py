"""Kalitlarsiz, offline tekshiruv: CSV yuklash + regex parse + saralash + shablon javob.

Telegram/Gemini kalitlari shart EMAS. Ishga tushirish: python smoke_test.py
"""
from __future__ import annotations

import ai
import sheets
from recommender import recommend


def section(title: str) -> None:
    print(f"\n{'=' * 60}\n{title}\n{'=' * 60}")


def main() -> None:
    section("1) Baza yuklash (sample_data.csv)")
    phones = sheets.get_phones()
    print(f"Yuklangan telefonlar: {len(phones)}")
    assert phones, "Baza bo'sh — sample_data.csv topilmadi?"
    p = phones[0]
    print(f"Birinchisi: {p.title()} | RAM={p.ram} | narx={p.price}")

    print(f"proc_tier o'qildi? birinchi telefon proc_tier={phones[0].proc_tier} "
          f"(Snapdragon 8 Gen 3 = 100 kutilgan)")

    queries = [
        "5 mln gacha Samsung",
        "5 mln atrofida telefon",
        "protsessor bo'yicha eng zo'ri",
        "eng arzon 10 ta telefon",
    ]

    for q in queries:
        section(f"So'rov: {q!r}")
        f = ai.parse_query(q)
        print(f"Filtr: brand={f.brand} color={f.color} price_max={f.price_max} "
              f"price_target={f.price_target} sort_by={f.sort_by} limit={f.limit}")
        top, relaxed = recommend(phones, f, limit=5)
        print(f"Topildi: {len(top)} ta (relaxed={relaxed})")
        if f.price_target:
            print(f"  Band: {int(f.price_target*0.6):,}".replace(",", " ")
                  + f" - {int(f.price_target*1.4):,}".replace(",", " ") + " oralig'i")
        print(ai.simple_reply(top))

    section("Tugma simulyatsiyasi: '5 mln atrofida Samsung' -> har xil tugma")
    from dataclasses import replace
    base = ai.parse_query("5 mln atrofida Samsung")
    for key, label in [("price_near", "🎯 Narxga yaqin"), ("camera", "📸 Kamera"),
                       ("processor", "🧠 Protsessor"), ("battery", "🔋 Batareyka")]:
        resorted = replace(base, sort_by=key)
        top, _ = recommend(phones, resorted, limit=3)
        names = " | ".join(f"{p.title()} ({p.price:,})".replace(",", " ") for p in top)
        print(f"[{label}] -> {names}")

    section("✅ Smoke test tugadi")


if __name__ == "__main__":
    main()
