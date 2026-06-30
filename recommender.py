"""Filtrlash + saralash mantiqi (LLM'siz, sof Python). Gemini faqat niyatni o'qiydi."""
from __future__ import annotations

from dataclasses import replace

from models import Phone, QueryFilter

# "X atrofida" so'ralganda narx oralig'i: target ±40%. Bundan uzoq narxlar ko'rsatilmaydi.
PRICE_BAND = 0.40


def _matches_hard(p: Phone, f: QueryFilter) -> bool:
    """Qattiq shartlar: biror shart buzilsa telefon tushib qoladi."""
    if f.brand and (p.brand or "").lower() != f.brand.lower():
        # iPhone uchun "apple"/"iphone" ikkalasini ham qabul qilamiz
        if not (f.brand.lower() in ("iphone", "apple") and (p.brand or "").lower() in ("iphone", "apple")):
            return False
    if f.os and (p.os or "").lower() != f.os.lower():
        return False
    if f.color and f.color.lower() not in (p.color or "").lower():
        return False
    if f.ram_min and (p.ram or 0) < f.ram_min:
        return False
    if f.storage_min and (p.storage or 0) < f.storage_min:
        return False
    if f.battery_min and (p.battery or 0) < f.battery_min:
        return False
    if f.price_max and p.price and p.price > f.price_max:
        return False
    if f.price_min and p.price and p.price < f.price_min:
        return False
    # "X atrofida": qattiq chegara berilmagan bo'lsa, target ±BAND oralig'i bilan cheklaymiz.
    if f.price_target and not f.price_max and p.price is not None:
        lo = f.price_target * (1 - PRICE_BAND)
        hi = f.price_target * (1 + PRICE_BAND)
        if not (lo <= p.price <= hi):
            return False
    return True


# Aniq saralash kalitlari: (key funksiyasi, kamayuvchimi).
# None qiymatlar har doim oxiriga tushadi.
_INF = float("inf")
_SORTERS = {
    "price_asc": (lambda p: p.price if p.price is not None else _INF, False),
    "price_desc": (lambda p: p.price or 0, True),
    "camera": (lambda p: p.camera_back or 0, True),
    "ram": (lambda p: p.ram or 0, True),
    "storage": (lambda p: p.storage or 0, True),
    "battery": (lambda p: p.battery or 0, True),
}


# Protsessor tier ballari (heuristik): chipset nomidagi kalit so'z bo'yicha taxminiy daraja.
# Yangi chipsetlar paydo bo'lsa shu jadvalga qo'shiladi.
_PROC_SCORES = {
    "snapdragon 8 gen 3": 100, "a17": 98, "snapdragon 8 gen 2": 95,
    "dimensity 9": 92, "snapdragon 8": 90, "a16": 88, "a15": 82,
    "dimensity 8": 80, "exynos 14": 70, "snapdragon 7": 68, "dimensity 7": 66,
    "snapdragon 6": 55, "dimensity 6": 53, "helio g99": 45, "helio g9": 42,
    "snapdragon 685": 40, "snapdragon 680": 38, "helio g85": 36, "helio g8": 34,
}


def _processor_score(name: str | None) -> int:
    """Chipset nomidan taxminiy quvvat bali (heuristik). Topilmasa 0."""
    if not name:
        return 0
    low = name.lower()
    best = 0
    for key, val in _PROC_SCORES.items():
        if key in low and val > best:
            best = val
    return best


def _proc_value(p: Phone) -> int:
    """Protsessor bali: Sheet'dagi proc_tier ustun bo'lsa shuni, aks holda nomdan taxmin."""
    if p.proc_tier is not None:
        return p.proc_tier
    return _processor_score(p.processor)


def _sort_phones(matched: list[Phone], f: QueryFilter) -> None:
    """matched ro'yxatini f.sort_by bo'yicha joyida saralaydi."""
    key = f.sort_by

    if key == "price_near" and f.price_target:
        target = f.price_target
        matched.sort(key=lambda p: abs((p.price if p.price is not None else _INF) - target))
        return
    if key == "processor":
        matched.sort(key=_proc_value, reverse=True)
        return

    sorter = _SORTERS.get(key or "")
    if sorter:
        key_fn, reverse = sorter
        matched.sort(key=key_fn, reverse=reverse)
        return

    matched.sort(key=lambda p: _score(p, f), reverse=True)


def _score(p: Phone, f: QueryFilter) -> float:
    """Yumshoq saralash bali — kattaroq = yaxshiroq mos."""
    score = 0.0
    if f.camera_priority == "high":
        score += (p.camera_back or 0) * 2.0
    if f.price_sensitive and p.price:
        # arzonroq = yuqoriroq bal (narxni manfiy hissa sifatida)
        score -= p.price / 1_000_000.0
    # umumiy "yaxshilik": ko'proq RAM/xotira/batareyka biroz ustun
    score += (p.ram or 0) * 0.5 + (p.storage or 0) * 0.02 + (p.battery or 0) * 0.001
    return score


def recommend(phones: list[Phone], f: QueryFilter, limit: int = 5) -> tuple[list[Phone], bool]:
    """Mos telefonlarni qaytaradi.

    Return: (telefonlar, relaxed) — relaxed=True bo'lsa qattiq shartlar topilmadi va
    yumshatilgan natija berildi (foydalanuvchini ogohlantirish uchun).
    """
    matched = [p for p in phones if _matches_hard(p, f)]
    relaxed = False

    if not matched:
        # Yumshatish: narx chegarasini olib tashlab, faqat brend/ram/rang bo'yicha urinish
        soft = QueryFilter(brand=f.brand, ram_min=f.ram_min, os=f.os, color=f.color,
                           camera_priority=f.camera_priority, price_sensitive=f.price_sensitive)
        matched = [p for p in phones if _matches_hard(p, soft)]
        relaxed = bool(matched)

    # "X atrofida" so'ralib, aniq saralash berilmagan bo'lsa — narxga yaqinlik default.
    eff = f
    if not f.sort_by and f.price_target:
        eff = replace(f, sort_by="price_near")

    _sort_phones(matched, eff)
    return matched[: (f.limit or limit)], relaxed
