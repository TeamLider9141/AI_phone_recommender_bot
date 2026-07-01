"""Lightweight checks for bot command handlers.

Run with: python3 test_bot_commands.py
"""
from __future__ import annotations

import asyncio
from datetime import date

import ai
import keyboards
import main
from models import Phone, QueryFilter


class FakeChat:
    id = 12345


class FakeBot:
    def __init__(self) -> None:
        self.deleted: list[tuple[int, int]] = []

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        self.deleted.append((chat_id, message_id))


class FakeMessage:
    def __init__(self, user_id: int = 12345) -> None:
        self.chat = FakeChat()
        self.from_user = type("FakeUser", (), {"id": user_id})()
        self.bot = FakeBot()
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.answers.append((text, reply_markup))


def test_bot_commands() -> None:
    commands = [command.command for command in main.bot_commands()]
    assert commands == ["start", "help", "clear", "reload"]


def test_startup_status_text() -> None:
    text = main.startup_status_text(500)
    assert "Bot ishlayapti" in text
    assert "500" in text


def test_admin_menu_has_settings_button() -> None:
    admin_markup = keyboards.main_menu_keyboard(is_admin=True)
    user_markup = keyboards.main_menu_keyboard(is_admin=False)

    admin_buttons = [button.text for row in admin_markup.keyboard for button in row]
    user_buttons = [button.text for row in user_markup.keyboard for button in row]

    assert "/settings" in admin_buttons
    assert "/settings" not in user_buttons


def test_phone_resolves_source_label() -> None:
    assert Phone(detail_url="https://texnomart.uz/product/detail/357642/").resolved_source_label() == "texno"
    assert Phone().resolved_source_label() == "baza"
    assert Phone(source_label="Texnomart").resolved_source_label() == "texno"


def test_source_block_renders_clickable_texno_link() -> None:
    phones = [
        Phone(
            brand="Samsung",
            model="Galaxy A06",
            detail_url="https://texnomart.uz/product/detail/357642/",
        ),
        Phone(brand="Xiaomi", model="Redmi 13"),
    ]

    reply = ai.append_source_block("Natija", phones)

    assert '<a href="https://texnomart.uz/product/detail/357642/">texno</a>' in reply
    assert "2. baza" in reply


def test_source_choice_keyboard_has_two_sources() -> None:
    markup = keyboards.source_choice_keyboard()
    button_texts = [button.text for row in markup.inline_keyboard for button in row]

    assert "📚 Baza" in button_texts
    assert "🛒 Texnomart" in button_texts


def test_results_keyboard_has_source_reset_button() -> None:
    markup = keyboards.results_keyboard(include_source_reset=True)
    button_texts = [button.text for row in markup.inline_keyboard for button in row]

    assert "🔎 Boshqa bazadan izlash" in button_texts


async def test_on_text_prompts_for_source_when_none_selected() -> None:
    old_selected = dict(main.USER_SELECTED_SOURCES)
    old_pending = dict(main.USER_PENDING_SEARCHES)
    old_last = dict(main.USER_LAST_SEARCHES)
    old_parse = main.ai.parse_query
    old_to_thread = main.asyncio.to_thread

    async def inline_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return func(*args, **kwargs)

    main.USER_SELECTED_SOURCES.clear()
    main.USER_PENDING_SEARCHES.clear()
    main.ai.parse_query = lambda text: QueryFilter(is_phone_related=True, brand="Samsung")
    main.asyncio.to_thread = inline_to_thread

    try:
        msg = FakeMessage()
        msg.text = "Samsung kerak"

        await main.on_text(msg)

        assert msg.answers
        text, markup = msg.answers[0]
        assert "qaysi bazadan" in text.lower()
        assert markup is not None
        assert msg.chat.id in main.USER_PENDING_SEARCHES
    finally:
        main.USER_SELECTED_SOURCES.clear()
        main.USER_SELECTED_SOURCES.update(old_selected)
        main.USER_PENDING_SEARCHES.clear()
        main.USER_PENDING_SEARCHES.update(old_pending)
        main.USER_LAST_SEARCHES.clear()
        main.USER_LAST_SEARCHES.update(old_last)
        main.ai.parse_query = old_parse
        main.asyncio.to_thread = old_to_thread


async def test_on_source_choice_remembers_selection_and_uses_pending_query() -> None:
    old_filters = dict(main.USER_FILTERS)
    old_selected = dict(main.USER_SELECTED_SOURCES)
    old_pending = dict(main.USER_PENDING_SEARCHES)
    old_last = dict(main.USER_LAST_SEARCHES)
    old_process = main._process

    async def fake_process(text, parsed_filter=None, source=None):  # noqa: ANN001
        return ("SOURCE OK", parsed_filter or QueryFilter(), True)

    main.USER_SELECTED_SOURCES.clear()
    main.USER_PENDING_SEARCHES.clear()
    main.USER_PENDING_SEARCHES[12345] = main.PendingSearch(
        text="Samsung kerak",
        parsed_filter=QueryFilter(is_phone_related=True, brand="Samsung"),
    )
    main._process = fake_process

    try:
        query = FakeCallbackQuery("source:set:texnomart", user_id=12345)
        await main.on_source_choice(query)

        assert main.USER_SELECTED_SOURCES[12345] == "texnomart"
        assert 12345 not in main.USER_PENDING_SEARCHES
        assert query.message.edits
        assert "SOURCE OK" in query.message.edits[0][0]
    finally:
        main.USER_FILTERS.clear()
        main.USER_FILTERS.update(old_filters)
        main.USER_SELECTED_SOURCES.clear()
        main.USER_SELECTED_SOURCES.update(old_selected)
        main.USER_PENDING_SEARCHES.clear()
        main.USER_PENDING_SEARCHES.update(old_pending)
        main.USER_LAST_SEARCHES.clear()
        main.USER_LAST_SEARCHES.update(old_last)
        main._process = old_process


async def test_process_reports_empty_texnomart_source_explicitly() -> None:
    old_get_phones = main.sheets.get_phones
    old_parse = main.ai.parse_query
    main.sheets.get_phones = lambda source=None: []  # noqa: ARG005
    main.ai.parse_query = lambda text: QueryFilter(is_phone_related=True, brand="Samsung")

    try:
        reply, f, has_results = await main._process("Samsung kerak", source="texnomart")

        assert has_results is False
        assert "texnomart" in reply.lower()
        assert f.brand == "Samsung"
    finally:
        main.sheets.get_phones = old_get_phones
        main.ai.parse_query = old_parse


async def test_reset_source_choice_clears_selection_and_reprompts() -> None:
    old_filters = dict(main.USER_FILTERS)
    old_selected = dict(main.USER_SELECTED_SOURCES)
    old_pending = dict(main.USER_PENDING_SEARCHES)
    old_last = dict(main.USER_LAST_SEARCHES)

    main.USER_SELECTED_SOURCES.clear()
    main.USER_PENDING_SEARCHES.clear()
    main.USER_SELECTED_SOURCES[12345] = "texnomart"

    try:
        query = FakeCallbackQuery("source:reset", user_id=12345)
        await main.on_source_choice(query)

        assert 12345 not in main.USER_SELECTED_SOURCES
        assert query.message.edits
        assert "qaysi bazadan" in query.message.edits[0][0].lower()
    finally:
        main.USER_FILTERS.clear()
        main.USER_FILTERS.update(old_filters)
        main.USER_SELECTED_SOURCES.clear()
        main.USER_SELECTED_SOURCES.update(old_selected)
        main.USER_PENDING_SEARCHES.clear()
        main.USER_PENDING_SEARCHES.update(old_pending)
        main.USER_LAST_SEARCHES.clear()
        main.USER_LAST_SEARCHES.update(old_last)


def test_daily_limit_for_non_admin_only() -> None:
    main.DAILY_USAGE.clear()
    day = date(2026, 6, 30)
    user_id = 777
    admin_id = 888
    old_admins = main.config.admin_ids
    main.config.admin_ids = [admin_id]
    old_limit = main.RUNTIME_SETTINGS.daily_limit
    main.RUNTIME_SETTINGS.daily_limit = 5

    try:
        assert [main.check_daily_limit(user_id, day) for _ in range(5)] == [True] * 5
        assert main.check_daily_limit(user_id, day) is False
        assert [main.check_daily_limit(admin_id, day) for _ in range(8)] == [True] * 8
        assert main.daily_usage_left(user_id, day) == 0
    finally:
        main.config.admin_ids = old_admins
        main.RUNTIME_SETTINGS.daily_limit = old_limit
        main.DAILY_USAGE.clear()


def test_daily_limit_settings_text() -> None:
    old_limit = main.RUNTIME_SETTINGS.daily_limit
    main.RUNTIME_SETTINGS.daily_limit = 7
    try:
        text = main.settings_text()
        assert "7" in text
        assert "UTC+5" in text
    finally:
        main.RUNTIME_SETTINGS.daily_limit = old_limit


def test_update_daily_limit_from_settings_action() -> None:
    old_limit = main.RUNTIME_SETTINGS.daily_limit
    main.RUNTIME_SETTINGS.daily_limit = 5
    try:
        assert main.update_daily_limit("+1") == 6
        assert main.update_daily_limit("-1") == 5
        assert main.update_daily_limit("10") == 10
        assert main.update_daily_limit("-1") == 9
    finally:
        main.RUNTIME_SETTINGS.daily_limit = old_limit


def test_settings_keyboard_has_off_topic_controls() -> None:
    markup = keyboards.settings_keyboard()
    callback_data = [button.callback_data for row in markup.inline_keyboard for button in row]

    assert any(cd.startswith("settings:blockmin:") for cd in callback_data)
    assert any(cd.startswith("settings:attempts:") for cd in callback_data)


def test_settings_text_shows_off_topic_config() -> None:
    old_minutes = main.RUNTIME_SETTINGS.off_topic_block_minutes
    old_attempts = main.RUNTIME_SETTINGS.off_topic_max_attempts
    main.RUNTIME_SETTINGS.off_topic_block_minutes = 45
    main.RUNTIME_SETTINGS.off_topic_max_attempts = 3
    try:
        text = main.settings_text()
        assert "45" in text
        assert "3 ta" in text
    finally:
        main.RUNTIME_SETTINGS.off_topic_block_minutes = old_minutes
        main.RUNTIME_SETTINGS.off_topic_max_attempts = old_attempts


def test_update_off_topic_settings_reconfigures_guard() -> None:
    old_minutes = main.RUNTIME_SETTINGS.off_topic_block_minutes
    old_attempts = main.RUNTIME_SETTINGS.off_topic_max_attempts
    try:
        assert main.update_off_topic_block_minutes("+15") == old_minutes + 15
        assert main.OFF_TOPIC_GUARD.block_seconds == (old_minutes + 15) * 60
        assert main.update_off_topic_max_attempts("+1") == old_attempts + 1
        assert main.OFF_TOPIC_GUARD.max_attempts == old_attempts + 1
    finally:
        main.update_off_topic_block_minutes(str(old_minutes))
        main.update_off_topic_max_attempts(str(old_attempts))


class FakeCallbackMessage:
    def __init__(self) -> None:
        self.edits: list[tuple[str, object | None]] = []

    async def edit_text(self, text: str, reply_markup=None) -> None:  # noqa: ANN001
        self.edits.append((text, reply_markup))


class FakeCallbackQuery:
    def __init__(self, data: str, user_id: int) -> None:
        self.data = data
        self.from_user = type("FakeUser", (), {"id": user_id})()
        self.message = FakeCallbackMessage()
        self.answers: list[tuple[str, bool]] = []

    async def answer(self, text: str = "", show_alert: bool = False) -> None:
        self.answers.append((text, show_alert))


async def test_on_settings_dispatches_blockmin_field() -> None:
    old_admins = main.config.admin_ids
    old_minutes = main.RUNTIME_SETTINGS.off_topic_block_minutes
    main.config.admin_ids = [999]
    try:
        query = FakeCallbackQuery("settings:blockmin:30", user_id=999)
        await main.on_settings(query)
        assert main.RUNTIME_SETTINGS.off_topic_block_minutes == 30
        assert "30" in query.answers[0][0]
        assert query.message.edits  # panel qayta chizildi
    finally:
        main.config.admin_ids = old_admins
        main.update_off_topic_block_minutes(str(old_minutes))


async def test_on_settings_rejects_non_admin() -> None:
    old_admins = main.config.admin_ids
    main.config.admin_ids = [999]
    try:
        query = FakeCallbackQuery("settings:daily:+1", user_id=1)
        await main.on_settings(query)
        assert query.answers[0][1] is True  # show_alert
        assert not query.message.edits
    finally:
        main.config.admin_ids = old_admins


async def test_clear_command() -> None:
    msg = FakeMessage()
    old_filters = dict(main.USER_FILTERS)
    old_results = {chat_id: list(message_ids) for chat_id, message_ids in main.USER_RESULT_MESSAGES.items()}
    old_selected = dict(main.USER_SELECTED_SOURCES)
    old_pending = dict(main.USER_PENDING_SEARCHES)
    old_last = dict(main.USER_LAST_SEARCHES)
    old_rate = {chat_id: list(times) for chat_id, times in main._RATE.items()}
    main.USER_FILTERS[msg.chat.id] = QueryFilter(brand="Samsung")
    main.USER_RESULT_MESSAGES[msg.chat.id] = [101, 102]
    main.USER_SELECTED_SOURCES[msg.chat.id] = "texnomart"
    main.USER_PENDING_SEARCHES[msg.chat.id] = main.PendingSearch(
        text="Samsung kerak",
        parsed_filter=QueryFilter(brand="Samsung"),
    )
    main.USER_LAST_SEARCHES[msg.chat.id] = main.PendingSearch(
        text="Samsung kerak",
        parsed_filter=QueryFilter(brand="Samsung"),
    )
    main._RATE[msg.chat.id] = [1.0, 2.0]

    await main.cmd_clear(msg)

    assert msg.chat.id not in main.USER_FILTERS
    assert msg.chat.id not in main.USER_RESULT_MESSAGES
    assert msg.chat.id not in main.USER_SELECTED_SOURCES
    assert msg.chat.id not in main.USER_PENDING_SEARCHES
    assert msg.chat.id not in main.USER_LAST_SEARCHES
    assert msg.chat.id not in main._RATE
    assert msg.bot.deleted == [(msg.chat.id, 101), (msg.chat.id, 102)]
    assert msg.answers
    assert "tozalandi" in msg.answers[0][0].lower()
    assert msg.answers[0][1] is not None

    main.USER_FILTERS.clear()
    main.USER_FILTERS.update(old_filters)
    main.USER_RESULT_MESSAGES.clear()
    main.USER_RESULT_MESSAGES.update(old_results)
    main.USER_SELECTED_SOURCES.clear()
    main.USER_SELECTED_SOURCES.update(old_selected)
    main.USER_PENDING_SEARCHES.clear()
    main.USER_PENDING_SEARCHES.update(old_pending)
    main.USER_LAST_SEARCHES.clear()
    main.USER_LAST_SEARCHES.update(old_last)
    main._RATE.clear()
    main._RATE.update(old_rate)


def main_test() -> None:
    test_bot_commands()
    test_startup_status_text()
    test_admin_menu_has_settings_button()
    test_phone_resolves_source_label()
    test_source_block_renders_clickable_texno_link()
    test_source_choice_keyboard_has_two_sources()
    test_results_keyboard_has_source_reset_button()
    test_daily_limit_for_non_admin_only()
    test_daily_limit_settings_text()
    test_update_daily_limit_from_settings_action()
    test_settings_keyboard_has_off_topic_controls()
    test_settings_text_shows_off_topic_config()
    test_update_off_topic_settings_reconfigures_guard()
    asyncio.run(test_on_text_prompts_for_source_when_none_selected())
    asyncio.run(test_on_source_choice_remembers_selection_and_uses_pending_query())
    asyncio.run(test_process_reports_empty_texnomart_source_explicitly())
    asyncio.run(test_reset_source_choice_clears_selection_and_reprompts())
    asyncio.run(test_on_settings_dispatches_blockmin_field())
    asyncio.run(test_on_settings_rejects_non_admin())
    asyncio.run(test_clear_command())
    print("bot command tests passed")


if __name__ == "__main__":
    main_test()
