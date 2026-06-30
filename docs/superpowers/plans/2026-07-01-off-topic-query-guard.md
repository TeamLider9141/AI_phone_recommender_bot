# Off-topic Query Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reject non-phone requests before recommendation generation and silently block a repeat offender for one hour after a second off-topic request within 60 minutes.

**Architecture:** Extend the existing structured Gemini parse with a required `is_phone_related` boolean and use a deterministic multilingual phone-term classifier as fallback. Keep strike/block transitions in a focused `topic_guard.py` service and enforce active blocks through aiogram outer middleware before any command, text, or callback handler.

**Tech Stack:** Python 3.10, aiogram 3.x, Google GenAI structured output, dataclasses, lightweight executable test scripts.

---

### Task 1: Add Topic Classification To Query Parsing

**Files:**
- Modify: `models.py`
- Modify: `ai.py`
- Create: `test_topic_guard.py`

- [ ] **Step 1: Write failing classification tests**

Create `test_topic_guard.py` with:

```python
"""Tests for phone-topic classification and off-topic blocking."""
from __future__ import annotations

import ai
import models


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


def main_test() -> None:
    test_phone_topic_classifier()
    test_fallback_parse_carries_topic_classification()
    test_gemini_schema_requires_topic_classification()
    print("topic guard tests passed")


if __name__ == "__main__":
    main_test()
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 test_topic_guard.py`

Expected: FAIL because `ai.is_phone_related_text` and `QueryFilter.is_phone_related` do not exist.

- [ ] **Step 3: Add the model and schema contract**

Add this field to `QueryFilter`:

```python
is_phone_related: bool = True
```

Add this property to `QUERY_FILTER_SCHEMA["properties"]`:

```python
"is_phone_related": {
    "type": "boolean",
    "description": "Faqat telefon/smartfon tanlash, narx, model, taqqoslash yoki xususiyatlar haqida bo'lsa true",
},
```

Add:

```python
"required": ["is_phone_related"],
```

Validate non-boolean model values in `QueryFilter.from_dict`:

```python
if "is_phone_related" in clean and not isinstance(clean["is_phone_related"], bool):
    clean.pop("is_phone_related")
```

- [ ] **Step 4: Implement deterministic classification and parser integration**

Add a public pure helper in `ai.py`:

```python
_PHONE_TOPIC_TERMS = (
    "telefon", "smartfon", "smartphone", "phone", "mobil", "android", "iphone",
    "ios", "kamera", "camera", "batareya", "batareyka", "battery", "ram",
    "xotira", "storage", "processor", "protsessor", "chipset", "snapdragon",
    "mediatek", "dimensity", "exynos",
)


def is_phone_related_text(text: str) -> bool:
    normalized = text.casefold()
    terms = (*_PHONE_TOPIC_TERMS, *_BRANDS)
    return any(
        re.search(rf"(?<!\w){re.escape(term)}(?!\w)", normalized)
        for term in terms
    )
```

Move `_BRANDS` above the helper or define the helper after `_BRANDS`. In
`_fallback_parse`, initialize:

```python
f = QueryFilter(
    free_text=text,
    is_phone_related=is_phone_related_text(text),
)
```

Extend `_PARSE_SYSTEM` with explicit positive and negative examples:

```text
- is_phone_related=true faqat telefon/smartfon tanlash, model, narx,
  taqqoslash yoki telefon xususiyatlari haqida bo'lsa.
- Ertak, inson ongi, ob-havo, siyosat, matematika va umumiy suhbat uchun
  is_phone_related=false qaytar va boshqa filtrlarni yozma.
```

After decoding Gemini JSON, recover safely if the field is absent or malformed:

```python
if not isinstance(data.get("is_phone_related"), bool):
    data["is_phone_related"] = is_phone_related_text(text)
```

- [ ] **Step 5: Run tests and verify GREEN**

Run: `python3 test_topic_guard.py`

Expected: classification tests PASS.

### Task 2: Implement Strike And Silent Block State

**Files:**
- Create: `topic_guard.py`
- Modify: `test_topic_guard.py`

- [ ] **Step 1: Write failing state-transition tests**

Add imports and tests:

```python
from topic_guard import OffTopicGuard


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
```

Call both tests from `main_test()` before printing the success message.

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 test_topic_guard.py`

Expected: FAIL because `topic_guard.OffTopicGuard` does not exist.

- [ ] **Step 3: Implement the state service**

Create `topic_guard.py` with:

```python
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
```

- [ ] **Step 4: Run tests and verify GREEN**

Run: `python3 test_topic_guard.py`

Expected: all classifier and state tests PASS.

### Task 3: Enforce Blocks Before Every Handler

**Files:**
- Modify: `topic_guard.py`
- Modify: `main.py`
- Modify: `test_topic_guard.py`
- Modify: `test_bot_commands.py`

- [ ] **Step 1: Write failing middleware and message-flow tests**

Add these imports:

```python
import asyncio

import main
from models import QueryFilter
from test_bot_commands import FakeMessage
from topic_guard import SilentBlockMiddleware
```

Add an async test proving a blocked update never reaches its handler:

```python
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
```

Add an integration-style test around `main.on_text`:

```python
async def test_off_topic_warning_then_silent_block_without_daily_usage() -> None:
    old_parse = main.ai.parse_query
    main.ai.parse_query = lambda text: QueryFilter(is_phone_related=False)
    main.OFF_TOPIC_GUARD.clear()
    main.DAILY_USAGE.clear()
    main._RATE.clear()
    try:
        first = FakeMessage(user_id=777)
        second = FakeMessage(user_id=777)
        await main.on_text(first)
        await main.on_text(second)
        assert len(first.answers) == 1
        assert "1 soat" in first.answers[0][0]
        assert second.answers == []
        assert main.OFF_TOPIC_GUARD.is_blocked(777)
        assert not any(key[0] == 777 for key in main.DAILY_USAGE)
    finally:
        main.ai.parse_query = old_parse
        main.OFF_TOPIC_GUARD.clear()
```

Call both async tests from `main_test()`:

```python
asyncio.run(test_silent_block_middleware_stops_updates())
asyncio.run(test_off_topic_warning_then_silent_block_without_daily_usage())
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python3 test_topic_guard.py`

Expected: FAIL because `SilentBlockMiddleware` and `main.OFF_TOPIC_GUARD` do not exist.

- [ ] **Step 3: Implement middleware**

Extend `topic_guard.py`:

```python
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class SilentBlockMiddleware(BaseMiddleware):
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
```

- [ ] **Step 4: Integrate classification without a second Gemini call**

In `main.py`, create:

```python
OFF_TOPIC_GUARD = OffTopicGuard()
```

Change `_process` to accept the already parsed filter:

```python
async def _process(text: str, parsed_filter: QueryFilter | None = None) -> tuple[str, QueryFilter, bool]:
    def work() -> tuple[str, QueryFilter, bool]:
        phones = sheets.get_phones()
        f = parsed_filter or ai.parse_query(text)
```

In `on_text`, parse before consuming the daily allowance:

```python
user_id = message.from_user.id if message.from_user else message.chat.id
try:
    parsed_filter = await asyncio.to_thread(ai.parse_query, message.text)
    if not parsed_filter.is_phone_related:
        action = OFF_TOPIC_GUARD.register_off_topic(user_id)
        if action == "warn":
            await message.answer(OFF_TOPIC_WARNING, reply_markup=_menu_for(message))
        return
    if not check_daily_limit(user_id):
        await message.answer(daily_limit_message(), reply_markup=_menu_for(message))
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    reply, f, has_results = await _process(message.text, parsed_filter)
except Exception:
    logger.exception("So'rovni qayta ishlashda xato")
    await message.answer(
        "Kechirasiz, xatolik yuz berdi. Birozdan keyin qayta urinib ko'ring.",
        reply_markup=_menu_for(message),
    )
    return
```

Register middleware before handlers:

```python
block_middleware = SilentBlockMiddleware(OFF_TOPIC_GUARD)
dp.message.outer_middleware(block_middleware)
dp.callback_query.outer_middleware(block_middleware)
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run: `python3 test_topic_guard.py`

Expected: all topic guard tests PASS.

Run: `python3 test_bot_commands.py`

Expected: existing command and daily-limit tests PASS.

### Task 4: Documentation And Full Verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Document the behavior**

Add this section:

```markdown
## Off-topic himoyasi

Bot tavsiya hisoblashdan oldin so'rov telefon mavzusiga aloqadorligini
tekshiradi. Birinchi aloqasiz so'rovda ogohlantirish beradi. Shu
ogohlantirishdan keyingi 60 daqiqada yana aloqasiz so'rov yuborilsa,
foydalanuvchi 1 soatga jim bloklanadi.

Blok vaqtida matn, komandalar va inline tugmalar javobsiz qoldiriladi. Qoida
adminlarga ham tegishli. Strike va bloklar xotirada saqlanadi, shu sababli bot
qayta ishga tushsa ular tozalanadi. Off-topic so'rovlar kunlik telefon so'rovi
limitidan foydalanmaydi.
```

- [ ] **Step 2: Run complete verification**

Run: `python3 test_topic_guard.py`

Expected: `topic guard tests passed`.

Run: `python3 test_bot_commands.py`

Expected: `bot command tests passed`.

Run: `python3 -m py_compile ai.py models.py topic_guard.py main.py test_topic_guard.py test_bot_commands.py`

Expected: exit code 0 with no output.

Run: `python3 smoke_test.py`

Expected: smoke test completes; when external services are unavailable, existing
CSV and regex fallback logs are acceptable.

Run: `git diff --check`

Expected: exit code 0 with no output.
