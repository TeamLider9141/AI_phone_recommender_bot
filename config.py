"""Konfiguratsiya: .env fayldan token/kalit/sozlamalarni o'qiydi."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    out: list[int] = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            out.append(int(part))
    return out


@dataclass
class Config:
    telegram_token: str
    gemini_api_key: str
    google_sheet_id: str
    google_credentials_path: str
    sheet_name: str            # ish varag'i (tab) nomi
    phone_source: str = "sheet"  # "sheet" | "texnomart"
    texnomart_base_url: str = "https://texnomart.uz/katalog/smartfony/"
    texnomart_max_pages: int = 0
    admin_ids: list[int] = field(default_factory=list)
    cache_ttl: int = 300       # soniya
    gemini_model: str = "gemini-2.0-flash"
    max_results: int = 20      # bitta javobда eng ko'pi bilan nechta telefon (abuse cap)
    rate_max: int = 15         # rate_window ichida ruxsat etilgan so'rov soni
    rate_window: int = 60      # rate limit oynasi (soniya)
    daily_limit: int = 5       # oddiy foydalanuvchi uchun kunlik so'rov limiti (UTC+5)
    off_topic_block_minutes: int = 60   # mavzuga aloqasiz so'rov uchun bloklash davomiyligi (daqiqa)
    off_topic_max_attempts: int = 2     # nechanchi ketma-ket off-topic urinish bloklaydi

    @property
    def ai_enabled(self) -> bool:
        return bool(self.gemini_api_key)


def load_config() -> Config:
    cfg = Config(
        telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
        gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
        google_sheet_id=os.getenv("GOOGLE_SHEET_ID", "").strip(),
        google_credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json").strip(),
        sheet_name=os.getenv("SHEET_NAME", "Sheet1").strip(),
        phone_source=os.getenv("PHONE_SOURCE", "sheet").strip().lower(),
        texnomart_base_url=os.getenv(
            "TEXNOMART_BASE_URL",
            "https://texnomart.uz/katalog/smartfony/",
        ).strip(),
        texnomart_max_pages=int(os.getenv("TEXNOMART_MAX_PAGES", "0")),
        admin_ids=_int_list(os.getenv("ADMIN_IDS")),
        cache_ttl=int(os.getenv("CACHE_TTL", "300")),
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash").strip(),
        max_results=int(os.getenv("MAX_RESULTS", "20")),
        rate_max=int(os.getenv("RATE_MAX", "15")),
        rate_window=int(os.getenv("RATE_WINDOW", "60")),
        daily_limit=int(os.getenv("DAILY_LIMIT", "5")),
        off_topic_block_minutes=int(os.getenv("OFF_TOPIC_BLOCK_MINUTES", "60")),
        off_topic_max_attempts=int(os.getenv("OFF_TOPIC_MAX_ATTEMPTS", "2")),
    )
    return cfg


# Modul darajasida bitta nusxa — boshqa modullar shundan oladi.
config = load_config()
