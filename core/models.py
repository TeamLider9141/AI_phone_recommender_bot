"""Ma'lumot strukturalari: Phone (bazadagi bitta telefon) va QueryFilter (so'rov filtri)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Phone:
    """Bazadagi (Google Sheet) bitta telefon yozuvi."""
    brand: Optional[str] = None
    model: Optional[str] = None
    ram: Optional[int] = None            # GB
    storage: Optional[int] = None        # GB
    color: Optional[str] = None
    camera_front: Optional[int] = None   # MP
    camera_back: Optional[int] = None    # MP
    processor: Optional[str] = None
    proc_tier: Optional[int] = None      # protsessor darajasi 1-100 (Sheet'da, ixtiyoriy)
    battery: Optional[int] = None        # mAh
    os: Optional[str] = None
    detail_url: Optional[str] = None
    source_label: Optional[str] = None    # "texno" yoki "baza"
    price: Optional[int] = None          # so'm yoki boshqa birlik

    def title(self) -> str:
        brand = (self.brand or "").strip()
        model = (self.model or "").strip()
        # Model brend nomi bilan boshlanса takrorlanmaslik uchun (masalan brand="iPhone" model="iPhone 13")
        if brand and model.lower().startswith(brand.lower()):
            return model if model else brand
        parts = [p for p in (brand, model) if p]
        return " ".join(parts) if parts else "Noma'lum telefon"

    def resolved_source_label(self) -> str:
        """Manba yorlig'ini qaytaradi: explicit label bo'lsa shuni, aks holda URL'dan taxmin qiladi."""
        label = (self.source_label or "").strip().lower()
        if label in {"texno", "texnomart", "texnomart.uz"}:
            return "texno"
        if label in {"baza", "base", "database", "db"}:
            return "baza"
        if label:
            return label
        if self.detail_url and "texnomart.uz" in self.detail_url.lower():
            return "texno"
        return "baza"

    def short_spec(self) -> str:
        """Telegram javobi uchun qisqa, o'qiladigan spetsifikatsiya satri."""
        bits: list[str] = []
        if self.ram:
            bits.append(f"{self.ram}GB RAM")
        if self.storage:
            bits.append(f"{self.storage}GB xotira")
        if self.camera_back:
            bits.append(f"{self.camera_back}MP kamera")
        if self.battery:
            bits.append(f"{self.battery}mAh")
        if self.os:
            bits.append(self.os)
        if self.color:
            bits.append(self.color)
        spec = " · ".join(bits)
        if self.price:
            spec = f"{spec}\n💰 {self.price:,} so'm".replace(",", " ")
        return spec


CameraPriority = str  # "none" | "low" | "high"


@dataclass
class QueryFilter:
    """Gemini foydalanuvchi matnidan ajratib oladigan strukturali filtr."""
    is_phone_related: bool = True
    brand: Optional[str] = None
    model: Optional[str] = None
    ram_min: Optional[int] = None
    storage_min: Optional[int] = None
    price_min: Optional[int] = None
    price_max: Optional[int] = None      # "X gacha" — qattiq yuqori chegara
    price_target: Optional[int] = None   # "X atrofida" — yaqinlik markazi (ikki tomon)
    os: Optional[str] = None
    color: Optional[str] = None
    battery_min: Optional[int] = None
    camera_priority: CameraPriority = "none"
    price_sensitive: bool = False        # "arzon" deb so'ralganmi
    sort_by: Optional[str] = None        # SORT_KEYS dan biri
    limit: Optional[int] = None          # "top 10" -> 10
    free_text: Optional[str] = None      # qolgan, structuredga tushmagan niyat
    # OR mantiqiy shartlar
    brand_options: list = field(default_factory=list)   # ["Samsung","Xiaomi"] — brand OR
    color_options: list = field(default_factory=list)   # ["qora","oq"] — color OR
    or_conditions: list = field(default_factory=list)   # [{"ram_min":16},{"storage_min":512}] — cross-param OR

    @classmethod
    def from_dict(cls, data: dict) -> "QueryFilter":
        """Gemini qaytargan JSON dict dan xavfsiz qurish (begona kalitlarni tashlab)."""
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {k: v for k, v in (data or {}).items()
                 if k in allowed and v is not None and v != "" and v != []}
        cp = clean.get("camera_priority")
        if cp not in ("none", "low", "high"):
            clean["camera_priority"] = "none"
        if "is_phone_related" in clean and not isinstance(clean["is_phone_related"], bool):
            clean.pop("is_phone_related")
        if clean.get("sort_by") not in SORT_KEYS:
            clean.pop("sort_by", None)
        # limit ni abuse cap bilan cheklaymiz (Gemini katta son qaytarsa ham)
        if "limit" in clean:
            from config import config
            try:
                clean["limit"] = max(1, min(int(clean["limit"]), config.max_results))
            except (TypeError, ValueError):
                clean.pop("limit", None)
        # List maydonlar: type tekshirish + or_conditions tozalash
        for lf in ("brand_options", "color_options"):
            if lf in clean and not isinstance(clean[lf], list):
                clean.pop(lf, None)
        if "or_conditions" in clean:
            ors = clean["or_conditions"]
            _valid = {"ram_min", "storage_min", "battery_min", "price_max", "price_min"}
            if isinstance(ors, list):
                clean["or_conditions"] = [
                    {k: int(v) for k, v in c.items() if k in _valid
                     and str(v).lstrip("-").isdigit()}
                    for c in ors if isinstance(c, dict)
                ]
                if not any(clean["or_conditions"]):
                    clean.pop("or_conditions")
            else:
                clean.pop("or_conditions")
        return cls(**clean)


# Ruxsat etilgan saralash kalitlari + foydalanuvchiga ko'rinadigan o'zbekcha nom.
# Tartib = tugmalar tartibi.
SORT_LABELS = {
    "price_near": "🎯 Narxga yaqin",
    "price_asc": "💰 Eng arzon",
    "price_desc": "💎 Eng qimmat",
    "camera": "📸 Kamera",
    "processor": "🧠 Protsessor",
    "ram": "⚡ RAM",
    "storage": "💾 Xotira",
    "battery": "🔋 Batareyka",
}
SORT_KEYS = set(SORT_LABELS)


# Gemini structured-output uchun JSON schema (response_schema).
QUERY_FILTER_SCHEMA = {
    "type": "object",
    "properties": {
        "is_phone_related": {
            "type": "boolean",
            "description": "Faqat telefon/smartfon tanlash, narx, model, taqqoslash yoki xususiyatlar haqida bo'lsa true",
        },
        "brand": {"type": "string", "description": "Telefon brendi, masalan Samsung, iPhone, Xiaomi"},
        "model": {"type": "string", "description": "Aniq model nomi agar aytilgan bo'lsa"},
        "ram_min": {"type": "integer", "description": "Minimal RAM (GB)"},
        "storage_min": {"type": "integer", "description": "Minimal xotira (GB)"},
        "price_min": {"type": "integer", "description": "Minimal narx (so'mda, raqam)"},
        "price_max": {"type": "integer", "description": "QATTIQ yuqori chegara: 'X gacha', 'X dan oshmasin'. '3 mln gacha' -> 3000000"},
        "price_target": {"type": "integer", "description": "Taxminiy narx markazi: 'X atrofida', 'X chamasi', 'X ga yaqin', '~X'. '5 mln atrofida' -> 5000000"},
        "os": {"type": "string", "description": "Operatsion tizim: Android yoki iOS"},
        "color": {"type": "string", "description": "Rang"},
        "battery_min": {"type": "integer", "description": "Minimal batareyka (mAh)"},
        "camera_priority": {
            "type": "string",
            "enum": ["none", "low", "high"],
            "description": "'kuchli/yaxshi kamera' -> high",
        },
        "price_sensitive": {"type": "boolean", "description": "'arzon', 'tejamkor' -> true"},
        "sort_by": {
            "type": "string",
            "enum": ["price_near", "price_asc", "price_desc", "camera", "processor", "ram", "storage", "battery"],
            "description": "Saralash: 'narxga yaqin'->price_near, 'eng arzon'->price_asc, "
                           "'eng qimmat'->price_desc, 'kamera bo'yicha'->camera, "
                           "'protsessor bo'yicha'->processor, 'ko'p ram'->ram, "
                           "'ko'p xotira'->storage, 'katta batareyka'->battery",
        },
        "limit": {"type": "integer", "description": "'top 10', 'top 20', 'eng arzon 5 ta' -> nechta natija"},
        "free_text": {"type": "string", "description": "Strukturaga tushmagan qo'shimcha niyat"},
        "brand_options": {
            "type": "array", "items": {"type": "string"},
            "description": "'Samsung yoki Xiaomi' → ['Samsung','Xiaomi']. Faqat 'yoki' orasida brand bo'lsa. brand bo'sh qoladi.",
        },
        "color_options": {
            "type": "array", "items": {"type": "string"},
            "description": "'qora yoki oq' → ['qora','oq']. Faqat 'yoki' orasida rang bo'lsa. color bo'sh qoladi.",
        },
        "or_conditions": {
            "type": "array", "items": {"type": "object"},
            "description": "Turli parametrlar uchun OR: '16GB RAM yoki 512GB xotira' → [{\"ram_min\":16},{\"storage_min\":512}]. "
                           "Faqat turli xil maydonlar yoki-langan bo'lsa.",
        },
    },
    "required": ["is_phone_related"],
}
