"""Telegram bot entrypoint (aiogram 3.x). Telefon tavsiya qiluvchi AI bot."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import replace

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message

import ai
import keyboards
import sheets
from config import config
from models import QueryFilter, SORT_LABELS
from recommender import recommend

# Foydalanuvchining oxirgi so'rov filtri (chat_id -> QueryFilter). Tugma bosilganda kerak.
USER_FILTERS: dict[int, QueryFilter] = {}

# Rate limit: har chat_id uchun so'rov vaqtlari (scraping/abuse'ga qarshi).
_RATE: dict[int, list[float]] = defaultdict(list)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bot")

RATE_MSG = "⏳ Juda ko'p so'rov yubordingiz. Iltimos birozdan keyin urinib ko'ring."
DUMP_NOTE = f"\n\n🔒 <i>Xavfsizlik uchun faqat eng mos {config.max_results} tasi ko'rsatiladi.</i>"


def _check_rate(chat_id: int) -> bool:
    """rate_window ichida rate_max dan oshmasa True. Oshsa False (cheklash)."""
    now = time.time()
    times = _RATE[chat_id]
    times[:] = [t for t in times if now - t < config.rate_window]
    if len(times) >= config.rate_max:
        return False
    times.append(now)
    return True

WELCOME = (
    "Assalomu alaykum! 👋\n\n"
    "Men telefon tanlashda yordam beraman. Sizga kerakli telefonni oddiy tilda yozing.\n\n"
    "Masalan:\n"
    "• <i>12 GB ramli, kuchli kamerali, 5 mln gacha Samsung kerak</i>\n"
    "• <i>arzon Xiaomi, katta batareyka</i>\n"
    "• <i>iPhone, 256 gb xotira</i>\n\n"
    "Yozing — eng mosini topib beraman 🔎"
)

RELAX_NOTE = "\n\n⚠️ <i>Aniq mos kelmadi, shu sababli shartlarni biroz yumshatib eng yaqinlarini berdim.</i>"


async def _process(text: str) -> tuple[str, QueryFilter, bool]:
    """So'rovni qayta ishlaydi. Return: (javob matni, filtr, natija_bormi).
    natija_bormi=False bo'lsa tugmalar ko'rsatilmaydi (topilmadi/bo'sh holat)."""
    def work() -> tuple[str, QueryFilter, bool]:
        phones = sheets.get_phones()
        f = ai.parse_query(text)
        if not phones:
            return "Baza hozircha bo'sh yoki yuklanmadi. Administrator bilan bog'laning.", f, False
        # So'ralgan brend bazada umuman yo'q bo'lsa — aniq "topilmadi".
        if f.brand and f.brand.lower() not in sheets.known_brands():
            return ai.NOT_FOUND, f, False
        top, relaxed = recommend(phones, f, limit=5)
        if not top:
            return ai.NOT_FOUND, f, False
        reply = ai.format_reply(top, f)
        if relaxed:
            has_price = bool(f.price_max or f.price_min or f.price_target)
            if has_price:
                wants_exp = (f.sort_by == "price_desc" or
                             bool(f.price_min and not f.price_max and not f.price_target))
                alt_f = QueryFilter(
                    brand=f.brand, os=f.os,
                    sort_by="price_desc" if wants_exp else "price_asc",
                )
                alt_top, _ = recommend(phones, alt_f, limit=5)
                note = "😔 Kechirasiz, bu narx oralig'idagi telefonlar bazamizda yo'q edi."
                label = ("💰 Bizdagi eng qimmat telefonlar:" if wants_exp
                         else "💰 Bizdagi eng arzon telefonlar:")
                reply = note + "\n\n" + ai.simple_reply(alt_top or top, label)
                f = alt_f
            else:
                reply += RELAX_NOTE
        if ai.is_dump_request(text):
            reply += DUMP_NOTE
        return reply, f, True

    return await asyncio.to_thread(work)


async def _resort(f: QueryFilter) -> str:
    """Tugma bosilganda: saqlangan filtrni qayta saralash (tez, Gemini'siz)."""
    def work() -> str:
        phones = sheets.get_phones()
        top, relaxed = recommend(phones, f, limit=f.limit or 5)
        title = SORT_LABELS.get(f.sort_by or "", "📱 Natijalar") + ":"
        reply = ai.simple_reply(top, title)
        if relaxed and top:
            reply += RELAX_NOTE
        return reply

    return await asyncio.to_thread(work)


async def cmd_start(message: Message) -> None:
    await message.answer(WELCOME)


async def cmd_reload(message: Message) -> None:
    if message.from_user is None or message.from_user.id not in config.admin_ids:
        await message.answer("⛔ Bu buyruq faqat administrator uchun.")
        return
    count = await asyncio.to_thread(sheets.refresh)
    await message.answer(f"♻️ Baza yangilandi: {count} ta telefon yuklandi.")


async def on_text(message: Message) -> None:
    if not message.text:
        return
    if not _check_rate(message.chat.id):
        await message.answer(RATE_MSG)
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        reply, f, has_results = await _process(message.text)
    except Exception:  # noqa: BLE001
        logger.exception("So'rovni qayta ishlashda xato")
        await message.answer("Kechirasiz, xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.")
        return

    if not has_results:
        await message.answer(reply)  # topilmadi — tugmalarsiz
        return

    USER_FILTERS[message.chat.id] = f
    active = f.sort_by or ("price_near" if f.price_target else None)
    await message.answer(reply, reply_markup=keyboards.results_keyboard(active=active))


async def on_sort(query: CallbackQuery) -> None:
    """Saralash tugmasi bosilganda: oldingi filtrni saqlab, faqat tartibni o'zgartirish."""
    if not _check_rate(query.message.chat.id):
        await query.answer(RATE_MSG, show_alert=True)
        return
    await query.answer()
    data = query.data or ""
    prefix, _, key = data.partition(":")
    base = USER_FILTERS.get(query.message.chat.id)
    if base is None:
        await query.message.answer("Avval kerakli telefonni yozib qidiring 🔎")
        return

    new_limit = 10 if prefix == "top" else (base.limit or 5)
    f = replace(base, sort_by=key, limit=new_limit)
    USER_FILTERS[query.message.chat.id] = f

    reply = await _resort(f)
    try:
        await query.message.edit_text(reply, reply_markup=keyboards.results_keyboard(active=key))
    except Exception:  # noqa: BLE001 — matn o'zgarmasa Telegram xato beradi, e'tibor bermaymiz
        pass


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_reload, Command("reload"))
    dp.message.register(on_text, F.text)
    dp.callback_query.register(on_sort, F.data.startswith(("sort:", "top:")))
    return dp


async def main() -> None:
    if not config.telegram_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN .env faylda ko'rsatilmagan.")
    if not config.ai_enabled:
        logger.warning("GEMINI_API_KEY yo'q — bot sodda (regex) rejimda ishlaydi.")

    # Startup'da bazani oldindan yuklab qo'yamiz (birinchi so'rov tez bo'lsin).
    await asyncio.to_thread(sheets.get_phones)

    bot = Bot(config.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()
    logger.info("Bot ishga tushdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
