"""Startup/restart bildirishnomasi uchun testlar.

Server restart bo'lganda admin xabar olishi kerak — hatto baza yuklanmasa ham.
Ilgari baza yuklash startup'ning eng birinchi qadami edi va u yiqilsa jarayon
Bot obyekti yaratilgunicha o'lardi: hech kim xabar olmasdi.

Run with: python3 -m tests.test_startup_notify (repo ildizidan)
"""
from __future__ import annotations

import asyncio

from bot import main
from core.config import config


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


def _with_admins(admin_ids, fn):
    old = config.admin_ids
    try:
        config.admin_ids = admin_ids
        return fn()
    finally:
        config.admin_ids = old


def test_startup_text_reports_loaded_database() -> None:
    text = main.startup_status_text(53)

    assert "53" in text
    assert "⚠️" not in text


def test_startup_text_flags_failed_database_load() -> None:
    text = main.startup_status_text(0, error="Sheets timeout")

    assert "⚠️" in text
    assert "Sheets timeout" in text


def test_notify_startup_sends_to_every_admin() -> None:
    bot = FakeBot()

    _with_admins([111, 222], lambda: asyncio.run(main.notify_startup(bot, 10)))

    assert [chat_id for chat_id, _ in bot.sent] == [111, 222]


def test_notify_startup_survives_send_failure() -> None:
    class BrokenBot(FakeBot):
        async def send_message(self, chat_id: int, text: str) -> None:
            if chat_id == 111:
                raise RuntimeError("chat topilmadi")
            await super().send_message(chat_id, text)

    bot = BrokenBot()

    # Birinchi admin yiqilsa ham ikkinchisiga xabar borishi kerak.
    _with_admins([111, 222], lambda: asyncio.run(main.notify_startup(bot, 10)))

    assert [chat_id for chat_id, _ in bot.sent] == [222]


def test_load_phones_for_startup_returns_error_instead_of_raising() -> None:
    old = main.sheets.get_phones
    try:
        def boom():
            raise RuntimeError("Sheets 503")

        main.sheets.get_phones = boom
        phones, error = asyncio.run(main.load_phones_for_startup())
    finally:
        main.sheets.get_phones = old

    assert phones == []
    assert error is not None and "Sheets 503" in error


def test_load_phones_for_startup_passes_through_on_success() -> None:
    old = main.sheets.get_phones
    try:
        main.sheets.get_phones = lambda: ["a", "b", "c"]
        phones, error = asyncio.run(main.load_phones_for_startup())
    finally:
        main.sheets.get_phones = old

    assert len(phones) == 3
    assert error is None


def main_test() -> None:
    test_startup_text_reports_loaded_database()
    test_startup_text_flags_failed_database_load()
    test_notify_startup_sends_to_every_admin()
    test_notify_startup_survives_send_failure()
    test_load_phones_for_startup_returns_error_instead_of_raising()
    test_load_phones_for_startup_passes_through_on_success()
    print("startup notify tests passed")


if __name__ == "__main__":
    main_test()
