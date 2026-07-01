"""Texnomart scraper uchun testlar.

Run with: python3 test_texnomart_scraper.py
"""
from __future__ import annotations

import sheets
import texnomart_scraper
from models import Phone


CATALOG_HTML = """
<div class="catalog">
  <article class="product-card">
    <a href="/product/detail/357642/">Samsung Galaxy A06 6/128GB Dark Blue</a>
    <div>Sharh yo‘q</div>
    <ul>
      <li>Ekran turi: PLS LCD</li>
      <li>Asosiy Kamera: 50 MP, 2 MP</li>
      <li>Old kamera: 8 MP</li>
      <li>Protsessor: MediaTek Helio G85</li>
      <li>Ichki xotira: 128 GB</li>
    </ul>
    <div>1 494 000 so'm</div>
  </article>
</div>
"""


def test_extracts_phone_from_catalog_html() -> None:
    phones = texnomart_scraper.extract_catalog_phones_from_html(
        CATALOG_HTML,
        base_url="https://texnomart.uz/katalog/smartfony/",
    )

    assert len(phones) == 1
    p = phones[0]
    assert p.brand == "Samsung"
    assert p.model == "Galaxy A06"
    assert p.ram == 6
    assert p.storage == 128
    assert p.color == "Dark Blue"
    assert p.camera_back == 50
    assert p.camera_front == 8
    assert p.processor == "MediaTek Helio G85"
    assert p.price == 1494000
    assert p.detail_url == "https://texnomart.uz/product/detail/357642/"
    assert p.source_label == "texno"


def test_load_phones_routes_to_texnomart_when_configured() -> None:
    old_source = sheets.config.phone_source
    old_base_url = sheets.config.texnomart_base_url
    old_loader = texnomart_scraper.scrape_catalog

    sentinel = [Phone(brand="Test", model="Phone", source_label="texno")]

    def fake_scrape_catalog(base_url: str, max_pages: int = 0, max_items: int = 0):  # noqa: ARG001
        return sentinel

    try:
        sheets.config.phone_source = "texnomart"
        sheets.config.texnomart_base_url = "https://texnomart.uz/katalog/smartfony/"
        texnomart_scraper.scrape_catalog = fake_scrape_catalog

        phones = sheets.load_phones()

        assert phones == sentinel
    finally:
        sheets.config.phone_source = old_source
        sheets.config.texnomart_base_url = old_base_url
        texnomart_scraper.scrape_catalog = old_loader


def test_load_phones_accepts_explicit_source_override() -> None:
    old_source = sheets.config.phone_source
    old_base_url = sheets.config.texnomart_base_url
    old_loader = texnomart_scraper.scrape_catalog

    sentinel = [Phone(brand="Override", model="Phone", source_label="texno")]

    def fake_scrape_catalog(base_url: str, max_pages: int = 0, max_items: int = 0):  # noqa: ARG001
        return sentinel

    try:
        sheets.config.phone_source = "sheet"
        sheets.config.texnomart_base_url = "https://texnomart.uz/katalog/smartfony/"
        texnomart_scraper.scrape_catalog = fake_scrape_catalog

        phones = sheets.load_phones(source="texnomart")

        assert phones == sentinel
    finally:
        sheets.config.phone_source = old_source
        sheets.config.texnomart_base_url = old_base_url
        texnomart_scraper.scrape_catalog = old_loader


def test_load_phones_returns_empty_for_empty_texnomart_scrape_without_fallback() -> None:
    old_source = sheets.config.phone_source
    old_base_url = sheets.config.texnomart_base_url
    old_loader = texnomart_scraper.scrape_catalog
    old_sheet_loader = sheets._load_from_sheet
    old_csv_loader = sheets._load_from_csv

    def fake_scrape_catalog(base_url: str, max_pages: int = 0, max_items: int = 0):  # noqa: ARG001
        return []

    def fail_if_called():  # noqa: ANN001
        raise AssertionError("fallback loader should not be called for texnomart source")

    try:
        sheets.config.phone_source = "texnomart"
        sheets.config.texnomart_base_url = "https://texnomart.uz/katalog/smartfony/"
        texnomart_scraper.scrape_catalog = fake_scrape_catalog
        sheets._load_from_sheet = fail_if_called
        sheets._load_from_csv = fail_if_called

        phones = sheets.load_phones(source="texnomart")

        assert phones == []
    finally:
        sheets.config.phone_source = old_source
        sheets.config.texnomart_base_url = old_base_url
        texnomart_scraper.scrape_catalog = old_loader
        sheets._load_from_sheet = old_sheet_loader
        sheets._load_from_csv = old_csv_loader


def test_scrape_catalog_default_page_limit_is_bounded() -> None:
    old_fetch = texnomart_scraper._fetch_html
    old_extract = texnomart_scraper.extract_catalog_phones_from_html
    fetched_urls: list[str] = []

    def fake_fetch(url: str, timeout: int = 20) -> str:  # noqa: ARG001
        fetched_urls.append(url)
        return "<html></html>"

    def fake_extract(html_text: str, base_url: str):  # noqa: ARG001
        return [Phone(brand="Oppo", model=f"Page {len(fetched_urls)}", detail_url=f"https://example.test/{len(fetched_urls)}")]

    try:
        texnomart_scraper._fetch_html = fake_fetch
        texnomart_scraper.extract_catalog_phones_from_html = fake_extract

        phones = texnomart_scraper.scrape_catalog(max_pages=0)

        assert len(phones) == texnomart_scraper.DEFAULT_MAX_PAGES
        assert texnomart_scraper.DEFAULT_MAX_PAGES <= 20
    finally:
        texnomart_scraper._fetch_html = old_fetch
        texnomart_scraper.extract_catalog_phones_from_html = old_extract


def test_scrape_catalog_stops_after_max_items() -> None:
    old_fetch = texnomart_scraper._fetch_html
    old_extract = texnomart_scraper.extract_catalog_phones_from_html
    fetched_urls: list[str] = []

    def fake_fetch(url: str, timeout: int = 20) -> str:  # noqa: ARG001
        fetched_urls.append(url)
        return "<html></html>"

    def fake_extract(html_text: str, base_url: str):  # noqa: ARG001
        page = len(fetched_urls)
        return [
            Phone(brand="Oppo", model=f"Page {page} A", detail_url=f"https://example.test/{page}-a"),
            Phone(brand="Oppo", model=f"Page {page} B", detail_url=f"https://example.test/{page}-b"),
        ]

    try:
        texnomart_scraper._fetch_html = fake_fetch
        texnomart_scraper.extract_catalog_phones_from_html = fake_extract

        phones = texnomart_scraper.scrape_catalog(max_pages=10, max_items=3)

        assert len(phones) == 3
        assert len(fetched_urls) == 2
    finally:
        texnomart_scraper._fetch_html = old_fetch
        texnomart_scraper.extract_catalog_phones_from_html = old_extract


def main_test() -> None:
    test_extracts_phone_from_catalog_html()
    test_load_phones_routes_to_texnomart_when_configured()
    test_load_phones_accepts_explicit_source_override()
    test_load_phones_returns_empty_for_empty_texnomart_scrape_without_fallback()
    test_scrape_catalog_default_page_limit_is_bounded()
    test_scrape_catalog_stops_after_max_items()
    print("texnomart scraper tests passed")


if __name__ == "__main__":
    main_test()
