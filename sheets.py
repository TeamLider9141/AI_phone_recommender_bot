"""Google Sheet (live) dan telefonlar bazasini o'qish + RAM cache (TTL).

Agar Google sozlamalari bo'lmasa (kalit/sheet_id yo'q), lokal `sample_data.csv`
ga tushadi — bu offline test va namuna uchun.
"""
from __future__ import annotations

import csv
import logging
import os
import re
import time
from io import StringIO
from typing import Optional
from urllib.parse import quote
from urllib.request import urlopen

from config import config
from models import Phone
import texnomart_cache
import texnomart_scraper

logger = logging.getLogger(__name__)

# Sheet header nomlarini Phone maydonlariga moslashtirish (moslashuvchan: registr/probel).
_FIELD_ALIASES = {
    "brand": "brand", "brend": "brand", "ishlabchiqaruvchi": "brand",
    "model": "model",
    "ram": "ram", "operativxotira": "ram",
    "storage": "storage", "xotira": "storage", "rom": "storage", "internalstorage": "storage",
    "color": "color", "rang": "color",
    "camerafront": "camera_front", "frontcamera": "camera_front", "oldikamera": "camera_front",
    "cameraback": "camera_back", "backcamera": "camera_back", "orqakamera": "camera_back", "asosiykamera": "camera_back",
    "processor": "processor", "protsessor": "processor", "cpu": "processor", "chipset": "processor",
    "proctier": "proc_tier", "protsessordarajasi": "proc_tier", "tier": "proc_tier", "cpurank": "proc_tier",
    "battery": "battery", "batareyka": "battery", "batareya": "battery", "akkumulyator": "battery",
    "os": "os", "operatsiontizim": "os",
    "detailurl": "detail_url", "url": "detail_url", "link": "detail_url",
    "sourcelabel": "source_label", "source": "source_label",
    "price": "price", "narx": "price", "narxi": "price",
}

_INT_FIELDS = {"ram", "storage", "camera_front", "camera_back", "battery", "price", "proc_tier"}

_cache_by_source: dict[str, list[Phone]] = {}
_loaded_at_by_source: dict[str, float] = {}

_SOURCE_ALIASES = {
    "sheet": "sheet",
    "baza": "sheet",
    "base": "sheet",
    "database": "sheet",
    "db": "sheet",
    "google": "sheet",
    "texnomart": "texnomart",
    "texno": "texnomart",
}


def _norm_key(key: str) -> str:
    return re.sub(r"[\s_\-\.]+", "", str(key).strip().lower())


def _to_int(value) -> Optional[int]:
    """'8 GB', '5,000,000', '5000mAh' -> int; bo'sh/xato -> None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"[^\d]", "", str(value))
    return int(digits) if digits else None


def _row_to_phone(row: dict) -> Phone:
    mapped: dict = {}
    for raw_key, raw_val in row.items():
        field = _FIELD_ALIASES.get(_norm_key(raw_key))
        if not field:
            continue
        val = (str(raw_val).strip() if raw_val is not None else "") or None
        if field in _INT_FIELDS:
            mapped[field] = _to_int(val)
        else:
            mapped[field] = val
    return Phone(**mapped)


def resolve_source(source: str | None = None) -> str:
    """Manba kalitini normallashtiradi: sheet yoki texnomart."""
    raw = (source or config.phone_source or "sheet").strip().lower()
    return _SOURCE_ALIASES.get(raw, raw if raw in {"sheet", "texnomart"} else "sheet")


def _load_from_sheet() -> list[Phone]:
    """Google Sheet'dan o'qiydi: credentials bo'lsa service account, bo'lmasa public CSV."""
    if os.path.exists(config.google_credentials_path):
        import gspread
        from google.oauth2.service_account import Credentials

        scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        creds = Credentials.from_service_account_file(config.google_credentials_path, scopes=scopes)
        client = gspread.authorize(creds)
        ws = client.open_by_key(config.google_sheet_id).worksheet(config.sheet_name)
        records = ws.get_all_records()  # 1-qator = header
        return [_row_to_phone(r) for r in records]

    # Public sheet: viewer share qilingan bo'lsa auth kerak emas.
    # gviz CSV endpoint tab nomi orqali ishlaydi.
    sheet = quote(config.sheet_name, safe="")
    url = (
        f"https://docs.google.com/spreadsheets/d/{config.google_sheet_id}/gviz/tq"
        f"?tqx=out:csv&sheet={sheet}"
    )
    with urlopen(url, timeout=20) as response:
        text = response.read().decode("utf-8")
    return [_row_to_phone(r) for r in csv.DictReader(StringIO(text))]


def _load_from_csv(path: str = "sample_data.csv") -> list[Phone]:
    if not os.path.exists(path):
        logger.warning("CSV fallback topilmadi: %s", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [_row_to_phone(r) for r in csv.DictReader(f)]


def _load_from_texnomart() -> list[Phone]:
    """Texnomart katalogini lokal cache orqali o'qiydi."""
    phones = texnomart_cache.load_cached_or_refresh(
        config.texnomart_cache_path,
        _scrape_texnomart,
        ttl_seconds=config.texnomart_cache_ttl,
    )
    logger.info("Texnomart'dan %d ta telefon yuklandi", len(phones))
    return phones


def _scrape_texnomart() -> list[Phone]:
    """Texnomart saytidan to'g'ridan-to'g'ri scrape qiladi."""
    return texnomart_scraper.scrape_catalog(
        base_url=config.texnomart_base_url,
        max_pages=config.texnomart_max_pages,
        max_items=config.texnomart_max_items,
    )


def load_phones(source: str | None = None) -> list[Phone]:
    """Manbadan telefonlar ro'yxatini yuklaydi (cachesiz, to'g'ridan-to'g'ri)."""
    resolved_source = resolve_source(source)
    if resolved_source == "texnomart":
        try:
            phones = _load_from_texnomart()
            if phones:
                return phones
            logger.warning("Texnomart scrape bo'sh qaytdi")
            return []
        except Exception:  # noqa: BLE001 — manba xatosi bo'lsa boshqa manbalarga tushamiz
            logger.exception("Texnomart scrape'da xato")
            return []

    if config.google_sheet_id:
        try:
            phones = _load_from_sheet()
            logger.info("Google Sheet'dan %d ta telefon yuklandi", len(phones))
            return phones
        except Exception:  # noqa: BLE001 — manba xatosi bo'lsa CSV ga tushamiz
            logger.exception("Sheet o'qishda xato, CSV fallback'ga o'tilyapti")
    phones = _load_from_csv()
    logger.info("CSV'dan %d ta telefon yuklandi", len(phones))
    return phones


def get_phones(source: str | None = None) -> list[Phone]:
    """Cache'langan ro'yxat; TTL o'tgan bo'lsa qayta yuklaydi."""
    resolved_source = resolve_source(source)
    loaded_at = _loaded_at_by_source.get(resolved_source, 0.0)
    if resolved_source not in _cache_by_source or (time.time() - loaded_at) > config.cache_ttl:
        _cache_by_source[resolved_source] = load_phones(resolved_source)
        _loaded_at_by_source[resolved_source] = time.time()
    return _cache_by_source[resolved_source]


def refresh(source: str | None = None) -> int:
    """Majburiy qayta yuklash (admin /reload). Yuklangan telefonlar sonini qaytaradi."""
    resolved_source = resolve_source(source)
    if resolved_source == "texnomart":
        _cache_by_source[resolved_source] = texnomart_cache.refresh_cache(
            config.texnomart_cache_path,
            _scrape_texnomart,
        )
    else:
        _cache_by_source[resolved_source] = load_phones(resolved_source)
    _loaded_at_by_source[resolved_source] = time.time()
    return len(_cache_by_source[resolved_source])


def known_brands(source: str | None = None) -> set[str]:
    """Bazadagi mavjud brendlar to'plami (kichik harfda). 'Topilmadi' tekshiruvi uchun."""
    return {(p.brand or "").lower() for p in get_phones(source=source) if p.brand}
