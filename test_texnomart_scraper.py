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

    def fake_scrape_catalog(base_url: str, max_pages: int = 0):  # noqa: ARG001
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

    def fake_scrape_catalog(base_url: str, max_pages: int = 0):  # noqa: ARG001
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


def main_test() -> None:
    test_extracts_phone_from_catalog_html()
    test_load_phones_routes_to_texnomart_when_configured()
    test_load_phones_accepts_explicit_source_override()
    print("texnomart scraper tests passed")


if __name__ == "__main__":
    main_test()
