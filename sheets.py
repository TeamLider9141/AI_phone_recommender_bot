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
from typing import Optional

from config import config
from models import Phone

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
    "price": "price", "narx": "price", "narxi": "price",
}

_INT_FIELDS = {"ram", "storage", "camera_front", "camera_back", "battery", "price", "proc_tier"}

_cache: list[Phone] = []
_loaded_at: float = 0.0


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


def _load_from_sheet() -> list[Phone]:
    import gspread
    from google.oauth2.service_account import Credentials

    scopes = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
    creds = Credentials.from_service_account_file(config.google_credentials_path, scopes=scopes)
    client = gspread.authorize(creds)
    ws = client.open_by_key(config.google_sheet_id).worksheet(config.sheet_name)
    records = ws.get_all_records()  # 1-qator = header
    return [_row_to_phone(r) for r in records]


def _load_from_csv(path: str = "sample_data.csv") -> list[Phone]:
    if not os.path.exists(path):
        logger.warning("CSV fallback topilmadi: %s", path)
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return [_row_to_phone(r) for r in csv.DictReader(f)]


def load_phones() -> list[Phone]:
    """Manbadan telefonlar ro'yxatini yuklaydi (cachesiz, to'g'ridan-to'g'ri)."""
    use_sheets = bool(config.google_sheet_id and os.path.exists(config.google_credentials_path))
    if use_sheets:
        try:
            phones = _load_from_sheet()
            logger.info("Google Sheet'dan %d ta telefon yuklandi", len(phones))
            return phones
        except Exception:  # noqa: BLE001 — manba xatosi bo'lsa CSV ga tushamiz
            logger.exception("Sheet o'qishda xato, CSV fallback'ga o'tilyapti")
    phones = _load_from_csv()
    logger.info("CSV'dan %d ta telefon yuklandi", len(phones))
    return phones


def get_phones() -> list[Phone]:
    """Cache'langan ro'yxat; TTL o'tgan bo'lsa qayta yuklaydi."""
    global _cache, _loaded_at
    if not _cache or (time.time() - _loaded_at) > config.cache_ttl:
        _cache = load_phones()
        _loaded_at = time.time()
    return _cache


def refresh() -> int:
    """Majburiy qayta yuklash (admin /reload). Yuklangan telefonlar sonini qaytaradi."""
    global _cache, _loaded_at
    _cache = load_phones()
    _loaded_at = time.time()
    return len(_cache)
