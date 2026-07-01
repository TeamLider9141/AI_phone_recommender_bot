"""Off-topic so'rovlar uchun ogohlantirish va vaqtinchalik blok holati."""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

DEFAULT_BLOCK_MINUTES = 60
DEFAULT_MAX_ATTEMPTS = 2  # nechanchi off-topic urinishda bloklaydi


def off_topic_warning_text(block_minutes: int) -> str:
    return (
        "Kechirasiz, hozirgi so'rovingizni e'tiborsiz qoldirishga majburmiz. "
        f"Agar {block_minutes} daqiqa ichida yana telefonga aloqador bo'lmagan "
        f"so'rov yuborsangiz, bot sizni {block_minutes} daqiqa davomida "
        "e'tiborsiz qoldiradi."
    )


# Orqaga moslik uchun standart matn (statik import qiladigan joylar bo'lsa).
OFF_TOPIC_WARNING = off_topic_warning_text(DEFAULT_BLOCK_MINUTES)


@dataclass
class UserTopicState:
    strikes: int = 0
    first_strike_at: float | None = None
    blocked_until: float | None = None


class OffTopicGuard:
    """Off-topic so'rovlarni hisoblab, sozlanadigan chegaradan keyin bloklaydi.

    - `max_attempts`: nechanchi ketma-ket off-topic so'rov bloklashni ishga tushiradi.
    - `window_seconds`/`block_seconds`: strike oynasi va blok davomiyligi (bir xil
      qiymatga bog'langan, /settings'da bitta "daqiqa" sifatida ko'rinadi).
    """

    def __init__(
        self,
        window_seconds: float = DEFAULT_BLOCK_MINUTES * 60,
        block_seconds: float = DEFAULT_BLOCK_MINUTES * 60,
        max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    ) -> None:
        self._states: dict[int, UserTopicState] = {}
        self.window_seconds = window_seconds
        self.block_seconds = block_seconds
        self.max_attempts = max(1, max_attempts)

    def configure(
        self,
        *,
        window_seconds: float | None = None,
        block_seconds: float | None = None,
        max_attempts: int | None = None,
    ) -> None:
        """Ishlab turgan holatda sozlamalarni o'zgartiradi (/settings uchun)."""
        if window_seconds is not None:
            self.window_seconds = window_seconds
        if block_seconds is not None:
            self.block_seconds = block_seconds
        if max_attempts is not None:
            self.max_attempts = max(1, max_attempts)

    def clear(self) -> None:
        self._states.clear()

    def is_blocked(self, user_id: int, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        state = self._states.get(user_id)
        if state is None:
            return False
        if state.blocked_until is not None:
            if current < state.blocked_until:
                return True
            self._states.pop(user_id, None)
            return False
        if state.first_strike_at is not None and current - state.first_strike_at >= self.window_seconds:
            self._states.pop(user_id, None)
        return False

    def register_off_topic(
        self,
        user_id: int,
        now: float | None = None,
    ) -> Literal["warn", "blocked"]:
        current = time.monotonic() if now is None else now
        if self.is_blocked(user_id, current):
            return "blocked"
        state = self._states.get(user_id)
        if state is None:
            state = UserTopicState(first_strike_at=current)
            self._states[user_id] = state
        state.strikes += 1
        if state.strikes >= self.max_attempts:
            state.blocked_until = current + self.block_seconds
            return "blocked"
        return "warn"


class SilentBlockMiddleware(BaseMiddleware):
    """Bloklangan foydalanuvchi update'ini handlerlarga yetkazmaydi."""

    def __init__(
        self,
        guard: OffTopicGuard,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.guard = guard
        self.clock = clock

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        user_id = getattr(from_user, "id", None)
        if user_id is None:
            chat = getattr(event, "chat", None)
            user_id = getattr(chat, "id", None)
        if user_id is not None and self.guard.is_blocked(user_id, self.clock()):
            return None
        return await handler(event, data)
