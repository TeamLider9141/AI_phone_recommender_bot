"""Off-topic so'rovlar uchun ogohlantirish va vaqtinchalik blok holati."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Literal

STRIKE_WINDOW_SECONDS = 60 * 60
BLOCK_DURATION_SECONDS = 60 * 60
OFF_TOPIC_WARNING = (
    "Kechirasiz, hozirgi so'rovingizni e'tiborsiz qoldirishga majburmiz. "
    "Agar 1 soat ichida yana telefonga aloqador bo'lmagan so'rov yuborsangiz, "
    "bot sizni 1 soat davomida e'tiborsiz qoldiradi."
)


@dataclass
class UserTopicState:
    warned_at: float | None = None
    blocked_until: float | None = None


class OffTopicGuard:
    def __init__(self) -> None:
        self._states: dict[int, UserTopicState] = {}

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
        if state.warned_at is not None and current - state.warned_at >= STRIKE_WINDOW_SECONDS:
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
        if state and state.warned_at is not None:
            state.blocked_until = current + BLOCK_DURATION_SECONDS
            return "blocked"
        self._states[user_id] = UserTopicState(warned_at=current)
        return "warn"
