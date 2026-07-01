"""Bot foydalanuvchilarini lokal JSON faylda kuzatish."""
from __future__ import annotations

import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class BotUser:
    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None
    language_code: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    start_count: int = 0

    def display_name(self) -> str:
        parts = [part for part in (self.first_name, self.last_name) if part]
        name = " ".join(parts).strip()
        if self.username:
            handle = f"@{self.username}"
            return f"{name} ({handle})" if name else handle
        return name or str(self.user_id)


def _read_payload(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        return payload if isinstance(payload, dict) else {"users": {}}
    except FileNotFoundError:
        return {"users": {}}


def _write_payload(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _user_from_dict(raw: dict) -> BotUser:
    allowed = BotUser.__dataclass_fields__.keys()  # type: ignore[attr-defined]
    clean = {key: raw.get(key) for key in allowed if key in raw}
    return BotUser(**clean)


def upsert_user(
    path: str | Path,
    user_id: int,
    first_name: str | None = None,
    last_name: str | None = None,
    username: str | None = None,
    language_code: str | None = None,
    now: str | None = None,
) -> tuple[BotUser, bool]:
    """Userni yaratadi yoki yangilaydi. Return: (user, birinchi_marta_mi)."""
    db_path = Path(path)
    payload = _read_payload(db_path)
    users = payload.setdefault("users", {})
    key = str(user_id)
    existing = users.get(key)
    is_new = not isinstance(existing, dict)
    user = _user_from_dict(existing) if isinstance(existing, dict) else BotUser(user_id=user_id)

    user.first_name = first_name
    user.last_name = last_name
    user.username = username
    user.language_code = language_code
    if is_new:
        user.first_seen = now
    user.last_seen = now
    user.start_count += 1
    users[key] = asdict(user)
    _write_payload(db_path, payload)
    return user, is_new


def load_users(path: str | Path) -> list[BotUser]:
    payload = _read_payload(Path(path))
    users = payload.get("users", {})
    if not isinstance(users, dict):
        return []
    return [_user_from_dict(raw) for raw in users.values() if isinstance(raw, dict)]


def new_user_admin_text(user: BotUser) -> str:
    username = f"@{html.escape(user.username)}" if user.username else "-"
    language = html.escape(user.language_code or "-")
    return (
        "👤 <b>Yangi user /start bosdi</b>\n\n"
        f"ID: <code>{user.user_id}</code>\n"
        f"Ism: <b>{html.escape(user.display_name())}</b>\n"
        f"Username: {username}\n"
        f"Til: {language}\n"
        f"Vaqt: {html.escape(user.first_seen or '-')}"
    )


def about_users_text(path: str | Path, limit: int = 10) -> str:
    users = sorted(load_users(path), key=lambda user: user.last_seen or "", reverse=True)
    lines = [
        "👥 <b>About users</b>",
        "",
        f"Jami userlar: {len(users)}",
        "",
        f"Oxirgi {min(limit, len(users))} ta:",
    ]
    for index, user in enumerate(users[:limit], start=1):
        lines.append(
            f"{index}. {html.escape(user.display_name())} "
            f"— <code>{user.user_id}</code> "
            f"— /start: {user.start_count} "
            f"— {html.escape(user.last_seen or '-')}"
        )
    if not users:
        lines.append("Hali userlar yo'q.")
    return "\n".join(lines)
