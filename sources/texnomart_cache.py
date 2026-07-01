"""Texnomart telefonlarini lokal JSON cache'da saqlash."""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from core.models import Phone

logger = logging.getLogger(__name__)

CacheLoader = Callable[[], list[Phone]]
_refreshing: set[str] = set()
_refresh_lock = threading.Lock()


def _phone_from_dict(raw: dict) -> Phone:
    allowed = Phone.__dataclass_fields__.keys()  # type: ignore[attr-defined]
    return Phone(**{key: raw.get(key) for key in allowed if key in raw})


def _read_cache(path: Path) -> tuple[float, list[Phone]] | None:
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        generated_at = float(payload.get("generated_at", 0.0))
        rows = payload.get("phones", [])
        if not isinstance(rows, list):
            return None
        return generated_at, [_phone_from_dict(row) for row in rows if isinstance(row, dict)]
    except FileNotFoundError:
        return None
    except Exception:  # noqa: BLE001
        logger.exception("Texnomart cache o'qishda xato: %s", path)
        return None


def _write_cache(path: Path, phones: list[Phone], now: float | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": time.time() if now is None else now,
        "phones": [asdict(phone) for phone in phones],
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def refresh_cache(path: str | Path, loader: CacheLoader, now: float | None = None) -> list[Phone]:
    """Texnomart'ni loader orqali yangilab, JSON cache'ga yozadi."""
    cache_path = Path(path)
    phones = loader()
    if phones:
        _write_cache(cache_path, phones, now=now)
    return phones


def _start_background_refresh(path: Path, loader: CacheLoader) -> None:
    key = str(path.resolve())
    with _refresh_lock:
        if key in _refreshing:
            return
        _refreshing.add(key)

    def worker() -> None:
        try:
            refresh_cache(path, loader)
        except Exception:  # noqa: BLE001
            logger.exception("Texnomart cache background refresh xatosi")
        finally:
            with _refresh_lock:
                _refreshing.discard(key)

    thread = threading.Thread(target=worker, name="texnomart-cache-refresh", daemon=True)
    thread.start()


def load_cached_or_refresh(
    path: str | Path,
    loader: CacheLoader,
    ttl_seconds: int,
    now: float | None = None,
    background: bool = True,
) -> list[Phone]:
    """Fresh cache'ni qaytaradi; stale cache bo'lsa darhol qaytarib, orqada yangilaydi."""
    cache_path = Path(path)
    current = time.time() if now is None else now
    cached = _read_cache(cache_path)
    if cached is None:
        return refresh_cache(cache_path, loader, now=current)

    generated_at, phones = cached
    is_fresh = ttl_seconds <= 0 or (current - generated_at) < ttl_seconds
    if is_fresh:
        return phones

    if background:
        _start_background_refresh(cache_path, loader)
        return phones
    refreshed = refresh_cache(cache_path, loader, now=current)
    return refreshed or phones
