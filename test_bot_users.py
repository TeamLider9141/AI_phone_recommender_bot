"""Bot user tracking storage tests.

Run with: python3 test_bot_users.py
"""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import bot_users


def test_upsert_user_tracks_first_and_repeat_start() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "bot_users.json"
        first, is_new = bot_users.upsert_user(
            path,
            user_id=10,
            first_name="Ali",
            last_name="Valiyev",
            username="ali",
            language_code="uz",
            now="2026-07-01T10:00:00+05:00",
        )
        second, is_new_again = bot_users.upsert_user(
            path,
            user_id=10,
            first_name="Ali",
            last_name="Valiyev",
            username="ali",
            language_code="uz",
            now="2026-07-01T10:05:00+05:00",
        )

        assert is_new is True
        assert is_new_again is False
        assert first.start_count == 1
        assert second.start_count == 2
        assert second.first_seen == "2026-07-01T10:00:00+05:00"
        assert second.last_seen == "2026-07-01T10:05:00+05:00"


def test_about_users_text_lists_recent_users() -> None:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "bot_users.json"
        bot_users.upsert_user(path, user_id=1, first_name="Ali", now="2026-07-01T10:00:00+05:00")
        bot_users.upsert_user(
            path,
            user_id=2,
            first_name="Vali",
            username="vali",
            language_code="uz",
            now="2026-07-01T10:10:00+05:00",
        )

        text = bot_users.about_users_text(path, limit=10)

        assert "Jami userlar: 2" in text
        assert "@vali" in text
        assert "Ali" in text


def main_test() -> None:
    test_upsert_user_tracks_first_and_repeat_start()
    test_about_users_text_lists_recent_users()
    print("bot users tests passed")


if __name__ == "__main__":
    main_test()
