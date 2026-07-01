"""Tests for phone-topic classification and off-topic blocking."""
from __future__ import annotations

import asyncio

import ai
import main
import models
from models import QueryFilter
from topic_guard import OffTopicGuard, SilentBlockMiddleware


class FakeChat:
    id = 4567


class FakeBot:
    def __init__(self) -> None:
        self.actions: list[tuple[int, object]] = []

    async def send_chat_action(self, chat_id: int, action: object) -> None:
        self.actions.append((chat_id, action))


class FakeMessage:
    def __init__(self, user_id: int) -> None:
        self.chat = FakeChat()
        self.from_user = type("FakeUser", (), {"id": user_id})()
        self.bot = FakeBot()
        self.text = "insonlar ongi haqida nimalarni bilasan?"
        self.answers: list[tuple[str, object | None]] = []

    async def answer(self, text: str, reply_markup=None):  # noqa: ANN001
        self.answers.append((text, reply_markup))
        return type("SentMessage", (), {"message_id": len(self.answers)})()


def test_phone_topic_classifier() -> None:
    related = [
        "5 mln gacha Samsung telefon kerak",
        "kamera yaxshi smartfon tavsiya qil",
        "iPhone 15 Pro bilan Pixel 9 ni solishtir",
        "bolshoy batareyali telefon",
        "best Android phone under 500 dollars",
    ]
    unrelated = [
        "insonlar ongi haqida nimalarni bilasan?",
        "menga ertak aytib ber",
        "bugun ob-havo qanday?",
        "2 + 2 nechchi?",
    ]

    assert all(ai.is_phone_related_text(text) for text in related)
    assert not any(ai.is_phone_related_text(text) for text in unrelated)


def test_fallback_parse_carries_topic_classification() -> None:
    assert ai._fallback_parse("Samsung telefon kerak").is_phone_related is True
    assert ai._fallback_parse("insonlar ongi haqida nimalarni bilasan?").is_phone_related is False


def test_gemini_schema_requires_topic_classification() -> None:
    assert models.QUERY_FILTER_SCHEMA["properties"]["is_phone_related"]["type"] == "boolean"
    assert "is_phone_related" in models.QUERY_FILTER_SCHEMA["required"]


def test_second_off_topic_inside_window_blocks_for_one_hour() -> None:
    guard = OffTopicGuard()

    assert guard.register_off_topic(7, now=100.0) == "warn"
    assert guard.register_off_topic(7, now=3699.0) == "blocked"
    assert guard.is_blocked(7, now=7298.0) is True
    assert guard.is_blocked(7, now=7299.0) is False


def test_expired_first_strike_starts_new_warning() -> None:
    guard = OffTopicGuard()

    assert guard.register_off_topic(7, now=100.0) == "warn"
    assert guard.register_off_topic(7, now=3700.0) == "warn"
    assert guard.is_blocked(7, now=3700.0) is False


def test_configurable_max_attempts_and_block_minutes() -> None:
    guard = OffTopicGuard(window_seconds=1800, block_seconds=1800, max_attempts=3)

    assert guard.register_off_topic(1, now=0.0) == "warn"
    assert guard.register_off_topic(1, now=1.0) == "warn"
    assert guard.register_off_topic(1, now=2.0) == "blocked"
    assert guard.is_blocked(1, now=1801.0) is True
    assert guard.is_blocked(1, now=1802.0) is False


def test_configure_updates_running_guard() -> None:
    guard = OffTopicGuard(window_seconds=3600, block_seconds=3600, max_attempts=2)
    guard.configure(window_seconds=60, block_seconds=60, max_attempts=1)

    assert guard.register_off_topic(9, now=0.0) == "blocked"
    assert guard.is_blocked(9, now=59.0) is True
    assert guard.is_blocked(9, now=61.0) is False


def test_settings_update_functions_reconfigure_guard() -> None:
    main.OFF_TOPIC_GUARD.clear()
    try:
        assert main.update_off_topic_block_minutes("30") == 30
        assert main.RUNTIME_SETTINGS.off_topic_block_minutes == 30
        assert main.OFF_TOPIC_GUARD.block_seconds == 30 * 60
        assert main.OFF_TOPIC_GUARD.window_seconds == 30 * 60

        assert main.update_off_topic_max_attempts("+1") == 3
        assert main.OFF_TOPIC_GUARD.max_attempts == 3

        assert main.update_off_topic_max_attempts("-10") == 1  # 1 dan kam bo'lmaydi
    finally:
        main.update_off_topic_block_minutes(str(60))
        main.update_off_topic_max_attempts(str(2))
        main.OFF_TOPIC_GUARD.clear()


async def test_silent_block_middleware_stops_updates() -> None:
    guard = OffTopicGuard()
    guard.register_off_topic(7, now=100.0)
    guard.register_off_topic(7, now=101.0)
    middleware = SilentBlockMiddleware(guard, clock=lambda: 102.0)
    called = False

    async def handler(event, data):  # noqa: ANN001
        nonlocal called
        called = True

    event = type("Event", (), {"from_user": type("User", (), {"id": 7})()})()
    await middleware(handler, event, {})

    assert called is False


async def test_off_topic_warning_then_silent_block_without_daily_usage() -> None:
    old_parse = main.ai.parse_query
    old_to_thread = main.asyncio.to_thread

    async def inline_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return func(*args, **kwargs)

    main.ai.parse_query = lambda text: QueryFilter(is_phone_related=False)
    main.asyncio.to_thread = inline_to_thread
    main.OFF_TOPIC_GUARD.clear()
    main.DAILY_USAGE.clear()
    main._RATE.clear()

    try:
        first = FakeMessage(user_id=777)
        second = FakeMessage(user_id=777)

        await main.on_text(first)
        await main.on_text(second)

        assert len(first.answers) == 1
        assert "60 daqiqa" in first.answers[0][0]
        assert second.answers == []
        assert main.OFF_TOPIC_GUARD.is_blocked(777)
        assert not any(key[0] == 777 for key in main.DAILY_USAGE)
    finally:
        main.ai.parse_query = old_parse
        main.asyncio.to_thread = old_to_thread
        main.OFF_TOPIC_GUARD.clear()
        main.DAILY_USAGE.clear()
        main._RATE.clear()


async def test_admin_is_exempt_from_off_topic_guard() -> None:
    old_parse = main.ai.parse_query
    old_to_thread = main.asyncio.to_thread
    old_admins = main.config.admin_ids
    old_process = main._process

    async def inline_to_thread(func, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        return func(*args, **kwargs)

    async def fake_process(text, parsed_filter=None):  # noqa: ANN001
        return ("ok", QueryFilter(is_phone_related=False), True)

    main.ai.parse_query = lambda text: QueryFilter(is_phone_related=False)
    main.asyncio.to_thread = inline_to_thread
    main.config.admin_ids = [777]
    main._process = fake_process
    main.OFF_TOPIC_GUARD.clear()
    main.DAILY_USAGE.clear()
    main._RATE.clear()

    try:
        admin_msg = FakeMessage(user_id=777)

        await main.on_text(admin_msg)

        assert not main.OFF_TOPIC_GUARD.is_blocked(777)
        assert admin_msg.answers
        assert admin_msg.answers[0][0] == "ok"  # off-topic ogohlantirishi emas, oddiy javob
    finally:
        main.ai.parse_query = old_parse
        main.asyncio.to_thread = old_to_thread
        main.config.admin_ids = old_admins
        main._process = old_process
        main.OFF_TOPIC_GUARD.clear()
        main.DAILY_USAGE.clear()
        main._RATE.clear()


def main_test() -> None:
    test_phone_topic_classifier()
    test_fallback_parse_carries_topic_classification()
    test_gemini_schema_requires_topic_classification()
    test_second_off_topic_inside_window_blocks_for_one_hour()
    test_expired_first_strike_starts_new_warning()
    test_configurable_max_attempts_and_block_minutes()
    test_configure_updates_running_guard()
    test_settings_update_functions_reconfigure_guard()
    asyncio.run(test_silent_block_middleware_stops_updates())
    asyncio.run(test_off_topic_warning_then_silent_block_without_daily_usage())
    asyncio.run(test_admin_is_exempt_from_off_topic_guard())
    print("topic guard tests passed")


if __name__ == "__main__":
    main_test()
