"""Inline tugmalar: natijalarni qayta saralash filtrlari."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import SORT_LABELS


def results_keyboard(active: str | None = None) -> InlineKeyboardMarkup:
    """So'rov natijasi ostidagi saralash tugmalari. active = belgilangan kalit."""
    b = InlineKeyboardBuilder()
    for key, label in SORT_LABELS.items():
        text = f"✅ {label}" if key == active else label
        b.button(text=text, callback_data=f"sort:{key}")
    b.adjust(2)  # 2 ta ustun
    b.row(InlineKeyboardButton(text="🔟 Top 10 arzon", callback_data="top:price_asc"))
    return b.as_markup()
