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
    """Admin uchun kunlik limit, off-topic bloklash vaqti va urinishlar sonini tez sozlash tugmalari."""
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="-1", callback_data="settings:daily:-1"),
        InlineKeyboardButton(text="+1", callback_data="settings:daily:+1"),
        InlineKeyboardButton(text="5", callback_data="settings:daily:5"),
        InlineKeyboardButton(text="10", callback_data="settings:daily:10"),
    )
    b.row(
        InlineKeyboardButton(text="-15 daq", callback_data="settings:blockmin:-15"),
        InlineKeyboardButton(text="+15 daq", callback_data="settings:blockmin:+15"),
        InlineKeyboardButton(text="30 daq", callback_data="settings:blockmin:30"),
        InlineKeyboardButton(text="60 daq", callback_data="settings:blockmin:60"),
    )
    b.row(
        InlineKeyboardButton(text="-1", callback_data="settings:attempts:-1"),
        InlineKeyboardButton(text="+1", callback_data="settings:attempts:+1"),
        InlineKeyboardButton(text="2", callback_data="settings:attempts:2"),
        InlineKeyboardButton(text="3", callback_data="settings:attempts:3"),
    )
    return b.as_markup()


def source_choice_keyboard() -> InlineKeyboardMarkup:
    """Telefon qidiruvi uchun manba tanlash tugmalari."""
    b = InlineKeyboardBuilder()
    b.row(
        InlineKeyboardButton(text="📚 Baza", callback_data="source:set:sheet"),
        InlineKeyboardButton(text="🛒 Texnomart", callback_data="source:set:texnomart"),
    )
    return b.as_markup()


def results_keyboard(active: str | None = None, include_source_reset: bool = False) -> InlineKeyboardMarkup:
    """So'rov natijasi ostidagi saralash tugmalari. active = belgilangan kalit."""
    b = InlineKeyboardBuilder()
    for key, label in SORT_LABELS.items():
        text = f"✅ {label}" if key == active else label
        b.button(text=text, callback_data=f"sort:{key}")
    b.adjust(2)  # 2 ta ustun
    b.row(InlineKeyboardButton(text="🔟 Top 10 arzon", callback_data="top:price_asc"))
    if include_source_reset:
        b.row(InlineKeyboardButton(text="🔎 Boshqa bazadan izlash", callback_data="source:reset"))
    return b.as_markup()
