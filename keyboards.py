"""Bot tugmalari: menyu va natijalarni qayta saralash filtrlari."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from models import SORT_LABELS


def main_menu_keyboard(is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Chat pastida ko'rinadigan asosiy buyruq tugmalari."""
    keyboard = [
        [KeyboardButton(text="/start"), KeyboardButton(text="/help")],
        [KeyboardButton(text="/clear")],
    ]
    if is_admin:
        keyboard.append([KeyboardButton(text="/settings")])
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Telefon so'rovingizni yozing...",
    )


def settings_keyboard() -> InlineKeyboardMarkup:
    """Admin uchun kunlik limitni tez sozlash tugmalari."""
    b = InlineKeyboardBuilder()
    b.button(text="-1", callback_data="settings:daily:-1")
    b.button(text="+1", callback_data="settings:daily:+1")
    b.button(text="5", callback_data="settings:daily:5")
    b.button(text="10", callback_data="settings:daily:10")
    b.adjust(2)
    return b.as_markup()


def results_keyboard(active: str | None = None) -> InlineKeyboardMarkup:
    """So'rov natijasi ostidagi saralash tugmalari. active = belgilangan kalit."""
    b = InlineKeyboardBuilder()
    for key, label in SORT_LABELS.items():
        text = f"✅ {label}" if key == active else label
        b.button(text=text, callback_data=f"sort:{key}")
    b.adjust(2)  # 2 ta ustun
    b.row(InlineKeyboardButton(text="🔟 Top 10 arzon", callback_data="top:price_asc"))
    return b.as_markup()
