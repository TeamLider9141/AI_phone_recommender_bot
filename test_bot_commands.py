"""Lightweight checks for bot command handlers.

Run with: python3 test_bot_commands.py
"""
from __future__ import annotations

import asyncio
from datetime import date

import keyboards
import main
from models import QueryFilter


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


async def test_clear_command() -> None:
    msg = FakeMessage()
    main.USER_FILTERS[msg.chat.id] = QueryFilter(brand="Samsung")
    main.USER_RESULT_MESSAGES[msg.chat.id] = [101, 102]
    main._RATE[msg.chat.id] = [1.0, 2.0]

    await main.cmd_clear(msg)

    assert msg.chat.id not in main.USER_FILTERS
    assert msg.chat.id not in main.USER_RESULT_MESSAGES
    assert msg.chat.id not in main._RATE
    assert msg.bot.deleted == [(msg.chat.id, 101), (msg.chat.id, 102)]
    assert msg.answers
    assert "tozalandi" in msg.answers[0][0].lower()
    assert msg.answers[0][1] is not None


def main_test() -> None:
    test_bot_commands()
    test_startup_status_text()
    test_admin_menu_has_settings_button()
    test_daily_limit_for_non_admin_only()
    test_daily_limit_settings_text()
    test_update_daily_limit_from_settings_action()
    asyncio.run(test_clear_command())
    print("bot command tests passed")


if __name__ == "__main__":
    main_test()
