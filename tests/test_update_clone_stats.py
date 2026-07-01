"""Tests for GitHub clone statistics updater."""
from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/update_clone_stats.py"
spec = importlib.util.spec_from_file_location("update_clone_stats", SCRIPT)
assert spec is not None and spec.loader is not None
update_clone_stats = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update_clone_stats)


def test_update_state_backfills_history_from_legacy_state() -> None:
    state = {"total": 88, "lastDate": "2026-06-30"}
    traffic = {
        "clones": [
            {"timestamp": "2026-06-29T00:00:00Z", "count": 4},
            {"timestamp": "2026-06-30T00:00:00Z", "count": 6},
        ]
    }

    new_state = update_clone_stats.update_state(state, traffic)

    assert new_state["total"] == 88
    assert new_state["lastDate"] == "2026-06-30"
    assert new_state["history"] == [
        {"date": "2026-06-29", "daily": 4, "cumulative": 82},
        {"date": "2026-06-30", "daily": 6, "cumulative": 88},
    ]


def test_update_state_backfills_then_adds_new_days_once() -> None:
    state = {"total": 88, "lastDate": "2026-06-30"}
    traffic = {
        "clones": [
            {"timestamp": "2026-06-30T00:00:00Z", "count": 6},
            {"timestamp": "2026-07-01T00:00:00Z", "count": 3},
        ]
    }

    new_state = update_clone_stats.update_state(state, traffic)

    assert new_state["total"] == 91
    assert new_state["lastDate"] == "2026-07-01"
    assert new_state["history"] == [
        {"date": "2026-06-30", "daily": 6, "cumulative": 88},
        {"date": "2026-07-01", "daily": 3, "cumulative": 91},
    ]


def test_update_state_adds_single_point_fallback_without_traffic() -> None:
    state = {"total": 88, "lastDate": "2026-06-30"}

    new_state = update_clone_stats.update_state(state, {"clones": []})

    assert new_state["total"] == 88
    assert new_state["lastDate"] == "2026-06-30"
    assert new_state["history"] == [
        {"date": "2026-06-30", "daily": 0, "cumulative": 88},
    ]


def main() -> None:
    test_update_state_backfills_history_from_legacy_state()
    test_update_state_backfills_then_adds_new_days_once()
    test_update_state_adds_single_point_fallback_without_traffic()
    print("clone stats tests passed")


if __name__ == "__main__":
    main()
