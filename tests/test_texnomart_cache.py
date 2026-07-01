"""Texnomart JSON cache uchun testlar.

Run with: python3 -m tests.test_texnomart_cache (repo ildizidan)
"""
from __future__ import annotations

import time
from pathlib import Path
from tempfile import TemporaryDirectory

from sources import texnomart_cache
from core.models import Phone


def test_refresh_cache_preserves_source_links() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "texnomart_cache.json"
        source = [
            Phone(
                brand="Oppo",
                model="Reno 12",
                price=5_300_000,
                detail_url="https://texnomart.uz/product/detail/123/",
                source_label="texno",
            )
        ]

        phones = texnomart_cache.refresh_cache(path, lambda: source, now=100.0)
        loaded = texnomart_cache.load_cached_or_refresh(
            path,
            lambda: [],
            ttl_seconds=3600,
            now=101.0,
            background=False,
        )

        assert phones == source
        assert len(loaded) == 1
        assert loaded[0].detail_url == "https://texnomart.uz/product/detail/123/"
        assert loaded[0].source_label == "texno"


def test_missing_cache_refreshes_synchronously() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "texnomart_cache.json"
        calls = 0

        def loader() -> list[Phone]:
            nonlocal calls
            calls += 1
            return [Phone(brand="Samsung", model="Galaxy A06", source_label="texno")]

        phones = texnomart_cache.load_cached_or_refresh(
            path,
            loader,
            ttl_seconds=3600,
            now=100.0,
            background=False,
        )

        assert calls == 1
        assert phones[0].brand == "Samsung"
        assert path.exists()


def test_stale_cache_returns_existing_data_and_refreshes_in_background() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "texnomart_cache.json"
        texnomart_cache.refresh_cache(
            path,
            lambda: [Phone(brand="Old", model="Phone", source_label="texno")],
            now=100.0,
        )

        def loader() -> list[Phone]:
            return [Phone(brand="New", model="Phone", source_label="texno")]

        phones = texnomart_cache.load_cached_or_refresh(
            path,
            loader,
            ttl_seconds=1,
            now=200.0,
            background=True,
        )

        assert phones[0].brand == "Old"
        for _ in range(50):
            refreshed = texnomart_cache.load_cached_or_refresh(
                path,
                lambda: [],
                ttl_seconds=3600,
                now=201.0,
                background=False,
            )
            if refreshed and refreshed[0].brand == "New":
                break
            time.sleep(0.02)
        assert refreshed[0].brand == "New"


def main_test() -> None:
    test_refresh_cache_preserves_source_links()
    test_missing_cache_refreshes_synchronously()
    test_stale_cache_returns_existing_data_and_refreshes_in_background()
    print("texnomart cache tests passed")


if __name__ == "__main__":
    main_test()
