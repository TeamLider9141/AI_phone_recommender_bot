"""Gemini (tekin) bilan ishlash: foydalanuvchi matnini filtrga aylantirish va javob yozish.

Gemini kaliti bo'lmasa yoki xato bo'lsa — oddiy qoidaviy (regex) fallback ishlaydi,
shu bois bot kalitsiz ham ishlaydi (sodda rejimda).

SDK: google-genai (yangi, google.generativeai deprecated).
"""
from __future__ import annotations

import json
import logging
import re

from config import config
from models import QUERY_FILTER_SCHEMA, Phone, QueryFilter

logger = logging.getLogger(__name__)

_PARSE_SYSTEM = """Sen telefon do'koni yordamchisisan. Foydalanuvchining o'zbekcha
(yoki rus/ingliz aralash) so'rovini O'QIB, qidiruv filtrini JSON ko'rinishida qaytar.
Qoidalar:
- Narxni so'mga aylantir: "3 mln"/"3 million" -> 3000000, "500 ming" -> 500000.
- "arzon", "tejamkor" -> price_sensitive=true (price_max yo'q bo'lsa ham).
- "kuchli/yaxshi/zo'r kamera" -> camera_priority="high".
- Aniq bo'lmagan maydonlarni QOLDIRMA (yozma). Faqat aytilganini yoz.
- iPhone -> brand="iPhone", os="iOS". Boshqa brendlar odatda os="Android"."""

_REPLY_SYSTEM = """Sen do'stona telefon-maslahatchisan. Berilgan telefonlar ro'yxati
asosida O'ZBEK TILIDA qisqa, chiroyli tavsiya yoz. Har bir telefonni 1 qatorda
brend+model, asosiy ustunligi va narxi bilan keltir. 2-3 jumla izoh qo'sh. Emoji
oz ishlat. Hech narsa to'qima — faqat berilgan ma'lumot.
MUHIM: Markdown belgilaridan (*, **, _, #) FOYDALANMA. Qalin matn kerak bo'lsa
faqat <b>...</b> HTML tegidan foydalan."""

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=config.gemini_api_key)
    return _client


# ---------- parse_query ----------

def parse_query(text: str) -> QueryFilter:
    """Tabiiy til so'rovini QueryFilter ga aylantiradi (Gemini, fallback regex)."""
    if config.ai_enabled:
        try:
            from google import genai
            from google.genai import types

            client = _get_client()
            resp = client.models.generate_content(
                model=config.gemini_model,
                contents=text,
                config=types.GenerateContentConfig(
                    system_instruction=_PARSE_SYSTEM,
                    response_mime_type="application/json",
                    response_schema=QUERY_FILTER_SCHEMA,
                    temperature=0,
                ),
            )
            data = json.loads(resp.text)
            return QueryFilter.from_dict(data)
        except Exception:  # noqa: BLE001
            logger.exception("Gemini parse xatosi, regex fallback ishlatilyapti")
    return _fallback_parse(text)


_BRANDS = ["samsung", "iphone", "apple", "xiaomi", "redmi", "realme", "oppo",
           "vivo", "honor", "huawei", "infinix", "tecno", "nokia", "oneplus", "poco",
           "motorola", "google", "nothing", "huawei"]
_COLORS = {"qora": "qora", "oq": "oq", "ko'k": "ko'k", "kok": "ko'k", "yashil": "yashil",
           "qizil": "qizil", "kulrang": "kulrang", "oltin": "oltin", "kumush": "kumush",
           "binafsha": "binafsha", "titan": "titan"}


def _fallback_parse(text: str) -> QueryFilter:
    t = text.lower()
    f = QueryFilter(free_text=text)

    for b in _BRANDS:
        if b in t:
            f.brand = "iPhone" if b in ("iphone", "apple") else b.capitalize()
            if b in ("iphone", "apple"):
                f.os = "iOS"
            break

    # RAM: "12 gb ram" / "8gb ram" / "ram 8"
    m = re.search(r"(\d{1,2})\s*(?:gb)?\s*ram", t) or re.search(r"ram\s*(\d{1,2})", t)
    if m:
        f.ram_min = int(m.group(1))

    # Narx: "atrofida/chamasi/yaqin" -> target, aks holda -> price_max
    price_val = _parse_price(t)
    if price_val:
        around = any(w in t for w in ("atrofida", "atrof", "chamasi", "taxminan",
                                      "qariyb", "yaqin", "~", "chama"))
        if around:
            f.price_target = price_val
        else:
            f.price_max = price_val
    if any(w in t for w in ("arzon", "tejamkor", "byudjet")):
        f.price_sensitive = True

    if any(w in t for w in ("kamera zo'r", "zor kamera", "kuchli kamera",
                             "yaxshi kamera", "kamera yaxshi", "kamera kuchli")):
        f.camera_priority = "high"

    for word, color in _COLORS.items():
        if word in t:
            f.color = color
            break

    # Saralash niyati
    if "eng arzon" in t or "arzonidan" in t:
        f.sort_by = "price_asc"
    elif "eng qimmat" in t or "qimmatidan" in t:
        f.sort_by = "price_desc"
    elif "narxga yaqin" in t or "narx bo'yicha yaqin" in t:
        f.sort_by = "price_near"
    elif "protsessor" in t or "processor" in t or "protssesor" in t:
        f.sort_by = "processor"
    elif "ko'p ram" in t or "kop ram" in t:
        f.sort_by = "ram"
    elif "ko'p xotira" in t or "kop xotira" in t:
        f.sort_by = "storage"
    elif "katta batareyka" in t or "katta batareya" in t:
        f.sort_by = "battery"

    # "top 10", "10 ta", "eng arzon 5 ta"
    m = re.search(r"(?:top\s*)?(\d{1,2})\s*ta\b", t) or re.search(r"top\s*(\d{1,2})", t)
    if m:
        f.limit = max(1, min(20, int(m.group(1))))

    return f


def _parse_price(t: str) -> int | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(mln|million|mil)\b", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000_000)
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(ming|tisyach|k)\b", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * 1_000)
    m = re.search(r"\b(\d{6,9})\b", t)
    if m:
        return int(m.group(1))
    return None


# ---------- format_reply ----------

def format_reply(phones: list[Phone], f: QueryFilter) -> str:
    """Top telefonlardan o'zbekcha tavsiya matni (Gemini, fallback shablon)."""
    if not phones:
        return _empty_reply(f)

    if config.ai_enabled:
        try:
            from google import genai
            from google.genai import types

            client = _get_client()
            payload = {
                "so'rov": f.free_text or "",
                "telefonlar": [_phone_dict(p) for p in phones],
            }
            resp = client.models.generate_content(
                model=config.gemini_model,
                contents=json.dumps(payload, ensure_ascii=False),
                config=types.GenerateContentConfig(
                    system_instruction=_REPLY_SYSTEM,
                    temperature=0.4,
                ),
            )
            txt = (resp.text or "").strip()
            if txt:
                return txt
        except Exception:  # noqa: BLE001
            logger.exception("Gemini format xatosi, shablon javob ishlatilyapti")

    return _template_reply(phones)


def _phone_dict(p: Phone) -> dict:
    return {
        "brand": p.brand, "model": p.model, "ram": p.ram, "storage": p.storage,
        "camera_back": p.camera_back, "battery": p.battery, "os": p.os,
        "color": p.color, "price": p.price, "processor": p.processor,
    }


def simple_reply(phones: list[Phone], title: str = "📱 Sizga mos telefonlar:") -> str:
    """Gemini'siz, tez shablon javob — tugma (qayta saralash) bosilganda ishlatiladi."""
    if not phones:
        return "Bu shartlar bo'yicha telefon topilmadi."
    return _template_reply(phones, title)


def _template_reply(phones: list[Phone], title: str = "📱 Sizga mos telefonlar:") -> str:
    lines = [title + "\n"]
    for i, p in enumerate(phones, 1):
        lines.append(f"{i}. <b>{p.title()}</b>\n{p.short_spec()}\n")
    return "\n".join(lines).strip()


def _empty_reply(f: QueryFilter) -> str:
    return (
        "Afsuski, so'rovingizga to'liq mos telefon topilmadi 😔\n"
        "Shartlarni biroz yumshatib ko'ring — masalan narx chegarasini oshiring "
        "yoki brendni o'zgartiring."
    )
