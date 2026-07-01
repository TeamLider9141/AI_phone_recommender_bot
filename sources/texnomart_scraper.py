"""Texnomart smartfonlar katalogi uchun yengil scraper.

Ushbu modul standart kutubxonalar bilan ishlaydi:
- katalog sahifasidan product detail linklarni oladi
- karta ichidagi title/spec/price'ni parse qiladi
- natijani Phone list ko'rinishida qaytaradi
"""
from __future__ import annotations

import html
import logging
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse, parse_qsl, urlencode, urlunparse
from urllib.request import Request, urlopen

from core.models import Phone

logger = logging.getLogger(__name__)

CATALOG_URL = "https://texnomart.uz/katalog/smartfony/"
DEFAULT_TIMEOUT = 20
DEFAULT_MAX_PAGES = 16
DEFAULT_MAX_ITEMS = 80

_TITLE_SPEC_RE = re.compile(
    r"^(?P<name>.+?)\s+(?P<ram>\d{1,2})\s*/\s*(?P<storage>\d{1,4})\s*(?:GB|Gb|ГБ)?"
    r"(?:\s+(?P<color>.+?))?(?:\s*\(.*\))?$",
    re.I,
)
_DETAIL_URL_RE = re.compile(r'href="(?P<href>/product/detail/\d+/)"')
# Bir qatorli narx: "1 170 000 so'm". Ko'p hollarda raqam va "so'm" alohida
# HTML elementida (alohida qatorda) keladi — bu holat _extract_price'da alohida
# tekshiriladi (butun blok matnini emas, qator-baqator ko'rib chiqib).
_INLINE_PRICE_RE = re.compile(r"^(\d[\d\s]*)\s*so['’‘]m$", re.I)
_PRICE_LINE_RE = re.compile(r"^so['’‘]m$", re.I)
_NUMBER_LINE_RE = re.compile(r"^\d[\d\s]*$")

# Katalog sahifasida ba'zan telefon bilan bir qatorda aksessuar kartalari ham
# chiqadi (himoya oynasi, chexol va h.k.) — bular telefon emas, chetlab o'tiladi.
_ACCESSORY_KEYWORDS = (
    "himoya oynasi", "himoya plyonkasi", "gidrogel", "chexol", "qopqoq",
    "zaryadlovchi", "quvvatlovchi qurilma", "kabel", "quloqchin", "naushnik",
    "simsiz quloqchin", "adapter", "kobura", "stilus", "stylus",
    "sim karta", "moslamasi", "kartridj", "flesh karta", "flesh-karta",
    "quvvat banki", "powerbank", "power bank",
)

# Ba'zi kartalarda title "Smartfon <Brand> ..." yoki "<Brand> ... Smartfoni"
# shaklida keladi — bu umumiy so'z brend/model/rang maydonlariga aralashib
# ketmasligi uchun oldin/keyin olib tashlanadi.
_GENERIC_LEADING_RE = re.compile(r"^(?:smartfon(?:i)?)\s+", re.I)
_GENERIC_TRAILING_RE = re.compile(r"\s+(?:smartfon(?:i)?)$", re.I)

_NOISE_PREFIXES = (
    "sharh", "savatchaga", "muddatli", "barcha xususiyatlar", "xususiyatlari",
    "tezkor ko'rish", "tezkor ko‘rish", "operatordan mavjudligini aniqlash",
    "kafolat", "chegirma", "bestseller", "tavsiya etiladi", "aksiya",
)
_SKIP_LINES = {
    "imei",
    "imei ni tekshirish",
    "savatchaga",
    "savatchada xozirda hech nima yo'q",
}

_BRAND_MAP = {
    "iphone": "iPhone",
    "apple": "Apple",
    "samsung": "Samsung",
    "xiaomi": "Xiaomi",
    "redmi": "Redmi",
    "poco": "Poco",
    "vivo": "Vivo",
    "honor": "Honor",
    "huawei": "Huawei",
    "oppo": "OPPO",
    "realme": "Realme",
    "infinix": "Infinix",
    "tecno": "TECNO",
    "nothing": "Nothing",
    "motorola": "Motorola",
    "google": "Google",
    "oneplus": "OnePlus",
    "nokia": "Nokia",
    "asus": "ASUS",
    "sony": "Sony",
    "lg": "LG",
}


class _TextExtractor(HTMLParser):
    """HTML dan ko'rinadigan matnni chiziqlar ko'rinishida chiqaradi."""

    _BLOCK_TAGS = {
        "article", "aside", "br", "div", "h1", "h2", "h3", "h4", "h5", "h6",
        "li", "p", "section", "tr", "td", "th", "ul", "ol",
    }
    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if tag in self._BLOCK_TAGS:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = html.unescape(data)
        if text:
            self._parts.append(text)

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = raw.replace("\xa0", " ").replace("\u200b", " ")
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n\s*\n+", "\n", raw)
        return raw.strip()


def _fetch_html(url: str, timeout: int = DEFAULT_TIMEOUT) -> str:
    req = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
            "Accept-Language": "uz,ru;q=0.8,en;q=0.5",
        },
    )
    with urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="ignore")


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\xa0", " ")).strip(" *•\t\r")


def _is_noise_line(line: str) -> bool:
    low = _clean_line(line).lower()
    if not low:
        return True
    if low in _SKIP_LINES:
        return True
    if low.startswith(_NOISE_PREFIXES):
        return True
    if low in {"ama", "yo'q", "ha", "no", "yes"}:
        return True
    if low.startswith("kod:"):
        return True
    if "so'm" in low or "so‘m" in low or "so’m" in low:
        return True
    if re.fullmatch(r"[\d\s\-]+", low):
        return True
    return False


def _extract_lines(html_text: str) -> list[str]:
    parser = _TextExtractor()
    parser.feed(html_text)
    parser.close()
    lines = [_clean_line(line) for line in parser.text().splitlines()]
    return [line for line in lines if line]


def _extract_detail_urls(html_text: str, base_url: str) -> list[str]:
    urls: list[str] = []
    seen: set[str] = set()
    for match in _DETAIL_URL_RE.finditer(html_text):
        href = urljoin(base_url, match.group("href"))
        if href not in seen:
            seen.add(href)
            urls.append(href)
    return urls


def _split_product_blocks(lines: list[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    started = False

    for raw_line in lines:
        line = _clean_line(raw_line)
        low = line.lower()
        if low in {"tezkor ko'rish", "tezkor ko‘rish"}:
            if current:
                blocks.append(current)
                current = []
            started = True
            continue
        if not started:
            continue
        current.append(line)

    if current:
        blocks.append(current)
    return blocks


def _is_title_candidate(line: str) -> bool:
    low = _clean_line(line).lower()
    if not low or _is_noise_line(low):
        return False
    if low.startswith("ekran turi") or low.startswith("asosiy kamera"):
        return False
    if low.startswith("old kamera") or low.startswith("protsessor"):
        return False
    if low.startswith("ichki xotira") or low.startswith("kameralar soni"):
        return False
    if low.startswith("review") or low.startswith("sarh") or low.startswith("sharh"):
        return False
    if low.startswith("image"):
        return False
    return True


def _extract_title(lines: list[str]) -> str | None:
    for line in lines:
        if _is_title_candidate(line):
            return _clean_line(line)
    return None


def _extract_price(lines: list[str]) -> int | None:
    """Narxni qator-baqator topadi (butun blokni birlashtirib emas — aks holda
    'Kameralar soni: 3' kabi oldingi qatordagi raqam narxga ulanib ketadi)."""
    for index, raw_line in enumerate(lines):
        line = _clean_line(raw_line)
        inline = _INLINE_PRICE_RE.match(line)
        if inline:
            digits = re.sub(r"[^\d]", "", inline.group(1))
            if digits:
                return int(digits)
            continue
        if _PRICE_LINE_RE.match(line) and index > 0:
            prev = _clean_line(lines[index - 1])
            if _NUMBER_LINE_RE.match(prev):
                digits = re.sub(r"[^\d]", "", prev)
                if digits:
                    return int(digits)
    return None


def _first_int(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


def _extract_labeled_value(lines: list[str], labels: tuple[str, ...]) -> str | None:
    labels_low = tuple(label.lower() for label in labels)
    for index, raw_line in enumerate(lines):
        line = _clean_line(raw_line)
        low = line.lower()
        if not any(low.startswith(label) for label in labels_low):
            continue
        if ":" in line:
            value = line.split(":", 1)[1].strip()
            if value:
                return value
        for next_line in lines[index + 1:]:
            candidate = _clean_line(next_line)
            if not candidate or _is_noise_line(candidate):
                continue
            return candidate
    return None


def _normalize_brand(raw: str) -> str:
    token = raw.strip()
    return _BRAND_MAP.get(token.lower(), token.capitalize())


def _strip_generic_marketing_words(text: str) -> str:
    """'Smartfon Huawei ...' / '... Smartfoni' kabi umumiy so'zlarni olib tashlaydi."""
    text = _GENERIC_LEADING_RE.sub("", text)
    text = _GENERIC_TRAILING_RE.sub("", text)
    return text.strip()


def _looks_like_accessory(title: str) -> bool:
    low = title.lower()
    return any(keyword in low for keyword in _ACCESSORY_KEYWORDS)


def _split_title(title: str) -> Phone:
    clean_title = _strip_generic_marketing_words(_clean_line(title))
    match = _TITLE_SPEC_RE.match(clean_title)

    name = clean_title
    ram = storage = None
    color = None
    if match:
        name = _clean_line(match.group("name"))
        ram = int(match.group("ram"))
        storage = int(match.group("storage"))
        color = _clean_line(match.group("color") or "") or None

    parts = name.split()
    brand = _normalize_brand(parts[0]) if parts else None
    model = None
    if len(parts) > 1:
        model = " ".join(parts[1:]).strip() or None

    return Phone(
        brand=brand,
        model=model,
        ram=ram,
        storage=storage,
        color=color,
    )


def _parse_product_block(lines: list[str], detail_url: str | None) -> Phone | None:
    title = _extract_title(lines)
    if not title or _looks_like_accessory(title):
        return None

    phone = _split_title(title)
    phone.detail_url = detail_url
    phone.source_label = "texno"

    phone.price = _extract_price(lines)
    phone.camera_back = _first_int(
        _extract_labeled_value(lines, ("Asosiy Kamera", "Asosiy kamera"))
    )
    phone.camera_front = _first_int(
        _extract_labeled_value(lines, ("Old kamera", "Old kamera"))
    )
    phone.processor = _extract_labeled_value(lines, ("Protsessor", "processor"))

    storage_value = _extract_labeled_value(lines, ("Ichki xotira", "Xotira", "Storage"))
    if phone.storage is None:
        phone.storage = _first_int(storage_value)

    ram_value = _extract_labeled_value(lines, ("Tezkor xotira (RAM)", "Tezkor xotira", "RAM"))
    if phone.ram is None:
        phone.ram = _first_int(ram_value)

    return phone


def extract_catalog_phones_from_html(html_text: str, base_url: str = CATALOG_URL) -> list[Phone]:
    """Katalog HTML'idan telefonlar ro'yxatini chiqaradi."""
    lines = _extract_lines(html_text)
    blocks = _split_product_blocks(lines)
    if not blocks and lines:
        blocks = [lines]
    detail_urls = _extract_detail_urls(html_text, base_url)

    phones: list[Phone] = []
    for index, block in enumerate(blocks):
        detail_url = detail_urls[index] if index < len(detail_urls) else None
        phone = _parse_product_block(block, detail_url)
        if phone:
            phones.append(phone)
    return phones


def _candidate_page_urls(base_url: str, page: int) -> list[str]:
    if page <= 1:
        return [base_url]

    parsed = urlparse(base_url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))

    query_variant = parsed._replace(query=urlencode({**query, "page": page}))
    query_url = urlunparse(query_variant)

    path = parsed.path.rstrip("/")
    path_variant = parsed._replace(path=f"{path}/page/{page}/", query=parsed.query)
    path_url = urlunparse(path_variant)

    return [query_url, path_url]


def scrape_catalog(
    base_url: str = CATALOG_URL,
    max_pages: int = 0,
    max_items: int = 0,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[Phone]:
    """Texnomart katalogini page by page scrape qiladi."""
    limit = max_pages if max_pages and max_pages > 0 else DEFAULT_MAX_PAGES
    item_limit = max_items if max_items and max_items > 0 else DEFAULT_MAX_ITEMS
    phones: list[Phone] = []
    seen: set[str] = set()

    for page in range(1, limit + 1):
        page_phones: list[Phone] = []
        last_error: Exception | None = None

        for page_url in _candidate_page_urls(base_url, page):
            try:
                html_text = _fetch_html(page_url, timeout=timeout)
                parsed = extract_catalog_phones_from_html(html_text, base_url=base_url)
                new_items = [phone for phone in parsed if (phone.detail_url or "") not in seen]
                if new_items:
                    page_phones = new_items
                    break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                logger.debug("Texnomart sahifa o'qishda xato: %s", page_url, exc_info=True)

        if not page_phones:
            if last_error is not None and not phones:
                raise last_error
            break

        phones.extend(page_phones)
        for phone in page_phones:
            if phone.detail_url:
                seen.add(phone.detail_url)
        if len(phones) >= item_limit:
            return phones[:item_limit]

    return phones
