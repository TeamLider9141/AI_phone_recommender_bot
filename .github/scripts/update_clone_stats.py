#!/usr/bin/env python3
"""GitHub Traffic API'dan klon statistikasini yig'ib, badge + o'sish grafigini yangilaydi.

GitHub Traffic API oxirgi 14 kunlik klon sonini beradi (undan uzoqrog'ini saqlamaydi),
shuning uchun bu skript har ishga tushganda faqat OLDIN hisoblanmagan kunlarni umumiy
songa qo'shadi (lastDate orqali kuzatiladi) va tarixni (history) alohida saqlaydi —
shu tarix asosida QuickChart'da o'sish grafigi chiziladi.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BADGE_FILE = REPO_ROOT / ".github/badges/clone-count.json"
STATE_FILE = REPO_ROOT / ".github/badges/clone-state.json"
README_FILE = REPO_ROOT / "README.md"
CHART_START = "<!-- CLONE_CHART:START -->"
CHART_END = "<!-- CLONE_CHART:END -->"
HISTORY_LIMIT = 60  # grafik URL uzunligini cheklash uchun oxirgi N kun


def fetch_traffic(repo: str, token: str) -> dict:
    url = f"https://api.github.com/repos/{repo}/traffic/clones"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"total": 0, "lastDate": "1970-01-01", "history": []}


def update_state(state: dict, traffic: dict) -> dict:
    last_date = state.get("lastDate", "1970-01-01")
    total = state.get("total", 0)
    history_by_date = {row["date"]: row for row in state.get("history", [])}
    new_last_date = last_date

    for entry in traffic.get("clones", []):
        day = entry["timestamp"][:10]
        count = entry["count"]
        if day > last_date:
            total += count
            history_by_date[day] = {"date": day, "daily": count, "cumulative": total}
            if day > new_last_date:
                new_last_date = day

    history = [history_by_date[d] for d in sorted(history_by_date)][-HISTORY_LIMIT:]
    return {"total": total, "lastDate": new_last_date, "history": history}


def write_badge(total: int) -> None:
    BADGE_FILE.write_text(
        json.dumps(
            {"schemaVersion": 1, "label": "clones", "message": str(total), "color": "blue"},
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )


def build_chart_url(history: list[dict]) -> str:
    labels = [row["date"][5:] for row in history]  # "MM-DD"
    data = [row["cumulative"] for row in history]
    config = {
        "type": "line",
        "data": {
            "labels": labels,
            "datasets": [
                {
                    "label": "Umumiy klonlar",
                    "data": data,
                    "borderColor": "#2563eb",
                    "backgroundColor": "rgba(37,99,235,0.15)",
                    "fill": True,
                    "tension": 0.3,
                    "pointRadius": 0,
                }
            ],
        },
        "options": {
            "plugins": {
                "legend": {"display": False},
                "title": {"display": True, "text": "Repo klonlari (kunlik yig'indi)"},
            },
            "scales": {"y": {"beginAtZero": True}},
        },
    }
    encoded = urllib.parse.quote(json.dumps(config, separators=(",", ":")))
    return f"https://quickchart.io/chart?c={encoded}&width=700&height=320&backgroundColor=white"


def update_readme(chart_url: str) -> None:
    text = README_FILE.read_text(encoding="utf-8")
    if CHART_START not in text or CHART_END not in text:
        return
    before, _, rest = text.partition(CHART_START)
    _, _, after = rest.partition(CHART_END)
    block = f"{CHART_START}\n![Klonlar grafigi]({chart_url})\n{CHART_END}"
    README_FILE.write_text(before + block + after, encoding="utf-8")


def main() -> None:
    repo = os.environ["REPO"]
    token = os.environ.get("GH_TOKEN", "")

    state = load_state()
    traffic = fetch_traffic(repo, token) if token else {"clones": []}

    new_state = update_state(state, traffic)
    STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_badge(new_state["total"])

    if new_state["history"]:
        update_readme(build_chart_url(new_state["history"]))

    print(f"Umumiy klon soni: {new_state['total']} (oxirgi hisoblangan sana: {new_state['lastDate']})")


if __name__ == "__main__":
    main()
