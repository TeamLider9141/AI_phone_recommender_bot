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
    price: Optional[int] = None          # so'm yoki boshqa birlik

    def title(self) -> str:
        brand = (self.brand or "").strip()
        model = (self.model or "").strip()
        # Model brend nomi bilan boshlanса takrorlanmaslik uchun (masalan brand="iPhone" model="iPhone 13")
        if brand and model.lower().startswith(brand.lower()):
            return model if model else brand
        parts = [p for p in (brand, model) if p]
        return " ".join(parts) if parts else "Noma'lum telefon"

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

    @classmethod
    def from_dict(cls, data: dict) -> "QueryFilter":
        """Gemini qaytargan JSON dict dan xavfsiz qurish (begona kalitlarni tashlab)."""
        allowed = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        clean = {k: v for k, v in (data or {}).items() if k in allowed and v not in ("", None)}
        cp = clean.get("camera_priority")
        if cp not in ("none", "low", "high"):
            clean["camera_priority"] = "none"
        if clean.get("sort_by") not in SORT_KEYS:
            clean.pop("sort_by", None)
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
        "limit": {"type": "integer", "description": "'top 10', 'eng arzon 5 ta' -> nechta natija"},
        "free_text": {"type": "string", "description": "Strukturaga tushmagan qo'shimcha niyat"},
    },
}
