"""Telegram bot entrypoint (aiogram 3.x). Telefon tavsiya qiluvchi AI bot."""
from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatAction, ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, Message

import ai
import bot_users
import keyboards
import sheets
from config import config
from models import QueryFilter, SORT_LABELS
from recommender import recommend
from topic_guard import OffTopicGuard, SilentBlockMiddleware, off_topic_warning_text

# Foydalanuvchining oxirgi so'rov filtri (chat_id -> QueryFilter). Tugma bosilganda kerak.
USER_FILTERS: dict[int, QueryFilter] = {}

# /clear uchun bot yuborgan oxirgi tavsiya xabarlari.
USER_RESULT_MESSAGES: dict[int, list[int]] = {}

# Tanlangan manba (chat_id -> "sheet" | "texnomart").
USER_SELECTED_SOURCES: dict[int, str] = {}

# Hozirgi va oxirgi so'rovlar: source tanlash va reset oqimi uchun.
@dataclass
class PendingSearch:
    text: str
    parsed_filter: QueryFilter


USER_PENDING_SEARCHES: dict[int, PendingSearch] = {}
USER_LAST_SEARCHES: dict[int, PendingSearch] = {}

# Rate limit: har chat_id uchun so'rov vaqtlari (scraping/abuse'ga qarshi).
_RATE: dict[int, list[float]] = defaultdict(list)

# Oddiy foydalanuvchilarning UTC+5 bo'yicha kunlik so'rov hisoblagichi.
UTC_PLUS_5 = timezone(timedelta(hours=5))


@dataclass
class RuntimeSettings:
    daily_limit: int
    off_topic_block_minutes: int
    off_topic_max_attempts: int


RUNTIME_SETTINGS = RuntimeSettings(
    daily_limit=max(1, config.daily_limit),
    off_topic_block_minutes=max(1, config.off_topic_block_minutes),
    off_topic_max_attempts=max(1, config.off_topic_max_attempts),
)
DAILY_USAGE: dict[tuple[int, date], int] = defaultdict(int)
OFF_TOPIC_GUARD = OffTopicGuard(
    window_seconds=RUNTIME_SETTINGS.off_topic_block_minutes * 60,
    block_seconds=RUNTIME_SETTINGS.off_topic_block_minutes * 60,
    max_attempts=RUNTIME_SETTINGS.off_topic_max_attempts,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("bot")

RATE_MSG = "⏳ Juda ko'p so'rov yubordingiz. Iltimos birozdan keyin urinib ko'ring."
DUMP_NOTE = f"\n\n🔒 <i>Xavfsizlik uchun faqat eng mos {config.max_results} tasi ko'rsatiladi.</i>"
STARTUP_TITLE = "Bot ishlayapti"
SOURCE_PROMPT_TEXT = "Qaysi bazadan telefonlar haqida ma'lumot beraylik?"
SOURCE_LABELS = {
    "sheet": "📚 Baza",
    "texnomart": "🛒 Texnomart",
}


def _check_rate(chat_id: int) -> bool:
    """rate_window ichida rate_max dan oshmasa True. Oshsa False (cheklash)."""
    now = time.time()
    times = _RATE[chat_id]
    times[:] = [t for t in times if now - t < config.rate_window]
    if len(times) >= config.rate_max:
        return False
    times.append(now)
    return True


def _source_choice_label(source: str | None) -> str:
    return SOURCE_LABELS.get(source or "", "📚 Baza")


def _callback_chat_id(query: CallbackQuery) -> int | None:
    message = query.message
    chat = getattr(message, "chat", None)
    if chat is not None:
        chat_id = getattr(chat, "id", None)
        if chat_id is not None:
            return chat_id
    if query.from_user and query.from_user.id is not None:
        return query.from_user.id
    return None


def _callback_message_id(query: CallbackQuery) -> int | None:
    return getattr(query.message, "message_id", None) if query.message is not None else None


def is_admin(user_id: int | None) -> bool:
    return user_id is not None and user_id in config.admin_ids


def utc_plus_5_date() -> date:
    return datetime.now(UTC_PLUS_5).date()


def daily_usage_left(user_id: int, day: date | None = None) -> int:
    if is_admin(user_id):
        return RUNTIME_SETTINGS.daily_limit
    current_day = day or utc_plus_5_date()
    used = DAILY_USAGE.get((user_id, current_day), 0)
    return max(0, RUNTIME_SETTINGS.daily_limit - used)


def check_daily_limit(user_id: int, day: date | None = None) -> bool:
    """So'rovga ruxsat beradi va oddiy foydalanuvchi hisoblagichini oshiradi."""
    if is_admin(user_id):
        return True

    current_day = day or utc_plus_5_date()
    stale_keys = [key for key in DAILY_USAGE if key[1] != current_day]
    for key in stale_keys:
        del DAILY_USAGE[key]

    usage_key = (user_id, current_day)
    if DAILY_USAGE[usage_key] >= RUNTIME_SETTINGS.daily_limit:
        return False
    DAILY_USAGE[usage_key] += 1
    return True


def _apply_delta_or_value(current: int, action: str) -> int:
    """"+N"/"-N" -> nisbiy o'zgarish, aks holda mutlaq qiymat sifatida o'qiladi."""
    if action and action[0] in "+-" and action[1:].isdigit():
        return current + int(action)
    try:
        return int(action)
    except ValueError:
        return current


def update_daily_limit(action: str) -> int:
    RUNTIME_SETTINGS.daily_limit = max(1, _apply_delta_or_value(RUNTIME_SETTINGS.daily_limit, action))
    return RUNTIME_SETTINGS.daily_limit


def update_off_topic_block_minutes(action: str) -> int:
    new_val = max(1, _apply_delta_or_value(RUNTIME_SETTINGS.off_topic_block_minutes, action))
    RUNTIME_SETTINGS.off_topic_block_minutes = new_val
    OFF_TOPIC_GUARD.configure(window_seconds=new_val * 60, block_seconds=new_val * 60)
    return new_val


def update_off_topic_max_attempts(action: str) -> int:
    new_val = max(1, _apply_delta_or_value(RUNTIME_SETTINGS.off_topic_max_attempts, action))
    RUNTIME_SETTINGS.off_topic_max_attempts = new_val
    OFF_TOPIC_GUARD.configure(max_attempts=new_val)
    return new_val


def settings_text() -> str:
    return (
        "⚙️ <b>Bot sozlamalari</b>\n\n"
        f"Oddiy foydalanuvchi uchun kunlik limit: <b>{RUNTIME_SETTINGS.daily_limit} ta</b>\n"
        f"Off-topic bloklash vaqti: <b>{RUNTIME_SETTINGS.off_topic_block_minutes} daqiqa</b>\n"
        f"Off-topic urinishlar soni (blokgacha): <b>{RUNTIME_SETTINGS.off_topic_max_attempts} ta</b>\n"
        "Hisoblanadigan vaqt zonasi: <b>UTC+5</b>\n\n"
        "1-qator — kunlik limit, 2-qator — bloklash vaqti (daqiqa), "
        "3-qator — urinishlar soni. Tugmalar orqali o'zgartiring."
    )


def daily_limit_message() -> str:
    return (
        f"⏳ Kunlik {RUNTIME_SETTINGS.daily_limit} ta so'rov limitingiz tugadi. "
        "UTC+5 bo'yicha yangi kun boshlanganda limit yangilanadi."
    )


def _menu_for(message: Message) -> object:
    user_id = message.from_user.id if message.from_user else None
    return keyboards.main_menu_keyboard(is_admin=is_admin(user_id))


WELCOME = (
    "Assalomu alaykum! 👋\n\n"
    "Men telefon tanlashda yordam beraman. Sizga kerakli telefonni oddiy tilda yozing.\n\n"
    "Avval sizdan qaysi manbadan qidirishni so'rayman: <b>✅Baza</b> yoki <b>✅Texnomart</b>.\n\n"
    "Masalan:\n"
    "• <i>12 GB ramli, kuchli kamerali, 5 mln gacha Samsung kerak</i>\n"
    "• <i>arzon Xiaomi, katta batareyka</i>\n"
    "• <i>iPhone, 256 gb xotira</i>\n\n"
    "Yozing — eng mosini topib beraman 🔎"
)

HELP_TEXT = (
    "Buyruqlar:\n"
    "/start — botni boshlash va menyuni ko'rsatish\n"
    "/help — qisqa qo'llanma\n"
    "/clear — oxirgi tavsiyalarni tozalash\n"
    "/reload — bazani yangilash (faqat admin)\n\n"
    "Telefon qidirganda bot avval qaysi bazadan foydalanishni so'raydi.\n"
    "Natija tagida \"boshqa bazadan izlash\" tugmasi ham bor.\n\n"
    "Oddiy foydalanuvchilar uchun kunlik so'rov limiti UTC+5 bo'yicha hisoblanadi.\n\n"
    "Telefon qidirish uchun oddiy yozing:\n"
    "<i>5 mln gacha Samsung</i>\n"
    "<i>kamera yaxshi, batareyasi katta telefon</i>\n"
    "<i>eng arzon 10 ta Xiaomi</i>"
)

RELAX_NOTE = "\n\n⚠️ <i>Aniq mos kelmadi, shu sababli shartlarni biroz yumshatib eng yaqinlarini berdim.</i>"


def bot_commands() -> list[BotCommand]:
    return [
        BotCommand(command="start", description="Botni boshlash"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="clear", description="Tavsiyalarni tozalash"),
        BotCommand(command="reload", description="Bazani yangilash"),
    ]


def startup_status_text(phone_count: int) -> str:
    return f"{STARTUP_TITLE}.\nBaza: {phone_count} ta telefon yuklandi."


async def setup_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(bot_commands())


async def notify_startup(bot: Bot, phone_count: int) -> None:
    if not config.admin_ids:
        return
    text = startup_status_text(phone_count)
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            logger.exception("Startup xabarini adminga yuborib bo'lmadi: %s", admin_id)


async def notify_new_user(bot: Bot, user: bot_users.BotUser) -> None:
    if not config.admin_ids:
        return
    text = bot_users.new_user_admin_text(user)
    for admin_id in config.admin_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:  # noqa: BLE001
            logger.exception("Yangi user xabarini adminga yuborib bo'lmadi: %s", admin_id)


async def track_start_user(message: Message) -> None:
    tg_user = message.from_user
    if tg_user is None:
        return
    now = datetime.now(UTC_PLUS_5).isoformat(timespec="seconds")
    user, is_new = bot_users.upsert_user(
        config.bot_users_path,
        user_id=tg_user.id,
        first_name=getattr(tg_user, "first_name", None),
        last_name=getattr(tg_user, "last_name", None),
        username=getattr(tg_user, "username", None),
        language_code=getattr(tg_user, "language_code", None),
        now=now,
    )
    if is_new:
        await notify_new_user(message.bot, user)


def _remember_result_message(chat_id: int, message_id: int) -> None:
    messages = USER_RESULT_MESSAGES.setdefault(chat_id, [])
    messages.append(message_id)


async def _process(
    text: str,
    parsed_filter: QueryFilter | None = None,
    source: str | None = None,
) -> tuple[str, QueryFilter, bool]:
    """So'rovni qayta ishlaydi. Return: (javob matni, filtr, natija_bormi).
    natija_bormi=False bo'lsa tugmalar ko'rsatilmaydi (topilmadi/bo'sh holat)."""
    def work() -> tuple[str, QueryFilter, bool]:
        phones = sheets.get_phones(source=source)
        f = parsed_filter or ai.parse_query(text)
        if not phones:
            if sheets.resolve_source(source) == "texnomart":
                return (
                    "🛒 Texnomart hozircha bo'sh yoki yuklanmadi. "
                    "Boshqa bazani tanlab ko'ring yoki keyinroq urinib ko'ring.",
                    f,
                    False,
                )
            return "Baza hozircha bo'sh yoki yuklanmadi. Administrator bilan bog'laning.", f, False
        # So'ralgan brend bazada umuman yo'q bo'lsa — aniq "topilmadi".
        if f.brand and f.brand.lower() not in sheets.known_brands(source=source):
            return ai.NOT_FOUND, f, False
        top, relaxed = recommend(phones, f, limit=5)
        if not top:
            return ai.NOT_FOUND, f, False
        reply = ai.format_reply(top, f)
        source_phones = top
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
                source_phones = alt_top or top
                f = alt_f
            else:
                reply += RELAX_NOTE
        if ai.is_dump_request(text):
            reply += DUMP_NOTE
        reply = ai.append_source_block(reply, source_phones)
        return reply, f, True

    return await asyncio.to_thread(work)


async def _resort(f: QueryFilter, source: str | None = None) -> str:
    """Tugma bosilganda: saqlangan filtrni qayta saralash (tez, Gemini'siz)."""
    def work() -> str:
        phones = sheets.get_phones(source=source)
        top, relaxed = recommend(phones, f, limit=f.limit or 5)
        title = SORT_LABELS.get(f.sort_by or "", "📱 Natijalar") + ":"
        reply = ai.simple_reply(top, title)
        if relaxed and top:
            reply += RELAX_NOTE
        reply = ai.append_source_block(reply, top)
        return reply

    return await asyncio.to_thread(work)


async def cmd_start(message: Message) -> None:
    await track_start_user(message)
    await message.answer(WELCOME, reply_markup=keyboards.source_choice_keyboard())


async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=_menu_for(message))


async def cmd_clear(message: Message) -> None:
    chat_id = message.chat.id
    message_ids = USER_RESULT_MESSAGES.pop(chat_id, [])
    for message_id in message_ids:
        try:
            await message.bot.delete_message(chat_id, message_id)
        except Exception:  # noqa: BLE001
            logger.debug("Tavsiya xabarini o'chirib bo'lmadi: chat=%s message=%s", chat_id, message_id)
    USER_FILTERS.pop(chat_id, None)
    USER_SELECTED_SOURCES.pop(chat_id, None)
    USER_PENDING_SEARCHES.pop(chat_id, None)
    USER_LAST_SEARCHES.pop(chat_id, None)
    _RATE.pop(chat_id, None)
    await message.answer(SOURCE_PROMPT_TEXT, reply_markup=keyboards.source_choice_keyboard())


async def cmd_reload(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        await message.answer("⛔ Bu buyruq faqat administrator uchun.", reply_markup=_menu_for(message))
        return
    count = await asyncio.to_thread(sheets.refresh)
    await message.answer(f"♻️ Baza yangilandi: {count} ta telefon yuklandi.", reply_markup=_menu_for(message))


async def cmd_settings(message: Message) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not is_admin(user_id):
        await message.answer("⛔ Bu buyruq faqat administrator uchun.", reply_markup=_menu_for(message))
        return
    await message.answer(settings_text(), reply_markup=keyboards.settings_keyboard())


async def on_text(message: Message) -> None:
    if not message.text:
        return
    if message.text.startswith("/"):
        return
    chat_id = message.chat.id
    if not _check_rate(message.chat.id):
        await message.answer(RATE_MSG, reply_markup=_menu_for(message))
        return

    user_id = message.from_user.id if message.from_user else message.chat.id
    try:
        parsed_filter = await asyncio.to_thread(ai.parse_query, message.text)

        selected_source = USER_SELECTED_SOURCES.get(chat_id)
        if not selected_source:
            # Manba hali tanlanmagan — so'rovni yo'qotmasdan saqlab qo'yamiz,
            # manba tanlangach avtomatik ishga tushadi (retype qildirmaslik uchun).
            pending = PendingSearch(text=message.text, parsed_filter=parsed_filter)
            USER_PENDING_SEARCHES[chat_id] = pending
            USER_LAST_SEARCHES[chat_id] = pending
            await message.answer(SOURCE_PROMPT_TEXT, reply_markup=keyboards.source_choice_keyboard())
            return

        if not parsed_filter.is_phone_related and not is_admin(user_id):
            action = OFF_TOPIC_GUARD.register_off_topic(user_id)
            if action == "warn":
                text = off_topic_warning_text(RUNTIME_SETTINGS.off_topic_block_minutes)
                await message.answer(text, reply_markup=_menu_for(message))
            return
        pending = PendingSearch(text=message.text, parsed_filter=parsed_filter)
        USER_PENDING_SEARCHES[chat_id] = pending
        USER_LAST_SEARCHES[chat_id] = pending

        if not check_daily_limit(user_id):
            await message.answer(daily_limit_message(), reply_markup=_menu_for(message))
            return

        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        reply, f, has_results = await _process(message.text, parsed_filter, source=selected_source)
    except Exception:  # noqa: BLE001
        logger.exception("So'rovni qayta ishlashda xato")
        await message.answer(
            "Kechirasiz, xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.",
            reply_markup=_menu_for(message),
        )
        return

    if not has_results:
        await message.answer(reply, reply_markup=keyboards.source_choice_keyboard())
        return

    USER_FILTERS[message.chat.id] = f
    USER_PENDING_SEARCHES.pop(message.chat.id, None)
    active = f.sort_by or ("price_near" if f.price_target else None)
    sent = await message.answer(
        reply,
        reply_markup=keyboards.results_keyboard(active=active, include_source_reset=True),
    )
    _remember_result_message(message.chat.id, sent.message_id)


async def on_source_choice(query: CallbackQuery) -> None:
    data = query.data or ""
    chat_id = _callback_chat_id(query)
    if chat_id is None:
        await query.answer()
        return

    if data == "source:reset":
        USER_SELECTED_SOURCES.pop(chat_id, None)
        USER_FILTERS.pop(chat_id, None)
        last_search = USER_LAST_SEARCHES.get(chat_id)
        if last_search is not None:
            USER_PENDING_SEARCHES[chat_id] = last_search
        else:
            USER_PENDING_SEARCHES.pop(chat_id, None)
        await query.answer()
        if query.message is not None:
            await query.message.edit_text(SOURCE_PROMPT_TEXT, reply_markup=keyboards.source_choice_keyboard())
        return

    parts = data.split(":")
    if len(parts) != 3 or parts[0] != "source" or parts[1] != "set":
        await query.answer()
        return

    source = sheets.resolve_source(parts[2])
    USER_SELECTED_SOURCES[chat_id] = source
    pending = USER_PENDING_SEARCHES.get(chat_id)
    if pending is None:
        await query.answer()
        if query.message is not None:
            await query.message.edit_text(
                f"✅ {_source_choice_label(source)} tanlandi. Endi so'rov yozing.",
            )
        return

    USER_LAST_SEARCHES[chat_id] = pending
    user_id = query.from_user.id if query.from_user else chat_id
    if not check_daily_limit(user_id):
        await query.answer(daily_limit_message(), show_alert=True)
        return

    try:
        reply, f, has_results = await _process(pending.text, pending.parsed_filter, source=source)
    except Exception:  # noqa: BLE001
        logger.exception("Source tanlashdagi so'rovni qayta ishlashda xato")
        await query.answer("Kechirasiz, xatolik yuz berdi. Birozdan keyin urinib ko'ring.", show_alert=True)
        return

    await query.answer()
    if query.message is None:
        if has_results:
            USER_FILTERS[chat_id] = f
            USER_PENDING_SEARCHES.pop(chat_id, None)
        return

    if not has_results:
        await query.message.edit_text(reply, reply_markup=keyboards.source_choice_keyboard())
        return

    USER_FILTERS[chat_id] = f
    USER_PENDING_SEARCHES.pop(chat_id, None)
    active = f.sort_by or ("price_near" if f.price_target else None)
    await query.message.edit_text(
        reply,
        reply_markup=keyboards.results_keyboard(active=active, include_source_reset=True),
    )
    message_id = _callback_message_id(query)
    if message_id is not None:
        _remember_result_message(chat_id, message_id)


async def on_settings(query: CallbackQuery) -> None:
    user_id = query.from_user.id if query.from_user else None
    if not is_admin(user_id):
        await query.answer("Faqat administrator uchun.", show_alert=True)
        return

    parts = (query.data or "").split(":")
    if len(parts) != 3:
        await query.answer()
        return
    _, field, action = parts

    if field == "daily":
        new_val = update_daily_limit(action)
        await query.answer(f"Kunlik limit: {new_val} ta")
    elif field == "blockmin":
        new_val = update_off_topic_block_minutes(action)
        await query.answer(f"Bloklash vaqti: {new_val} daqiqa")
    elif field == "attempts":
        new_val = update_off_topic_max_attempts(action)
        await query.answer(f"Urinishlar soni: {new_val} ta")
    elif field == "users" and action == "about":
        await query.answer("Userlar ro'yxati")
        if query.message:
            text = bot_users.about_users_text(config.bot_users_path)
            await query.message.edit_text(text, reply_markup=keyboards.settings_keyboard())
        return
    else:
        await query.answer()
        return

    if query.message:
        await query.message.edit_text(settings_text(), reply_markup=keyboards.settings_keyboard())


async def on_sort(query: CallbackQuery) -> None:
    """Saralash tugmasi bosilganda: oldingi filtrni saqlab, faqat tartibni o'zgartirish."""
    chat_id = _callback_chat_id(query)
    if chat_id is None or query.message is None:
        await query.answer()
        return
    if not _check_rate(chat_id):
        await query.answer(RATE_MSG, show_alert=True)
        return
    await query.answer()
    data = query.data or ""
    prefix, _, key = data.partition(":")
    base = USER_FILTERS.get(chat_id)
    if base is None:
        if hasattr(query.message, "answer"):
            await query.message.answer("Avval kerakli telefonni yozib qidiring 🔎")
        else:
            await query.answer("Avval kerakli telefonni yozib qidiring 🔎", show_alert=True)
        return

    new_limit = 10 if prefix == "top" else (base.limit or 5)
    f = replace(base, sort_by=key, limit=new_limit)
    USER_FILTERS[chat_id] = f

    reply = await _resort(f, source=USER_SELECTED_SOURCES.get(chat_id))
    try:
        await query.message.edit_text(
            reply,
            reply_markup=keyboards.results_keyboard(active=key, include_source_reset=True),
        )
    except Exception:  # noqa: BLE001 — matn o'zgarmasa Telegram xato beradi, e'tibor bermaymiz
        pass


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher()
    block_middleware = SilentBlockMiddleware(OFF_TOPIC_GUARD)
    dp.message.outer_middleware(block_middleware)
    dp.callback_query.outer_middleware(block_middleware)
    dp.message.register(cmd_start, CommandStart())
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(cmd_clear, Command("clear"))
    dp.message.register(cmd_reload, Command("reload"))
    dp.message.register(cmd_settings, Command("settings"))
    dp.message.register(on_text, F.text)
    dp.callback_query.register(on_source_choice, F.data.startswith("source:"))
    dp.callback_query.register(on_settings, F.data.startswith("settings:"))
    dp.callback_query.register(on_sort, F.data.startswith(("sort:", "top:")))
    return dp


async def main() -> None:
    if not config.telegram_token:
        raise SystemExit("TELEGRAM_BOT_TOKEN .env faylda ko'rsatilmagan.")
    if not config.ai_enabled:
        logger.warning("GEMINI_API_KEY yo'q — bot sodda (regex) rejimda ishlaydi.")

    # Startup'da bazani oldindan yuklab qo'yamiz (birinchi so'rov tez bo'lsin).
    phones = await asyncio.to_thread(sheets.get_phones)

    bot = Bot(config.telegram_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await setup_bot_commands(bot)
    await notify_startup(bot, len(phones))
    dp = build_dispatcher()
    logger.info("Bot ishga tushdi.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
