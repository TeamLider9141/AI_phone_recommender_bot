# Fixing the clone-count job (Unauthorized / 401)

This document collects the diagnosis and the concrete fixes to resolve the failing GitHub Actions job that updates clone statistics. It includes: why the job failed, how to fix repository secrets, a small workflow validation snippet, and an improved Python script you can commit.

---

## Summary of the failure

- The scheduled job `.github/workflows/clone-count.yml` fails with `urllib.error.HTTPError: HTTP Error 401: Unauthorized` when calling the GitHub Traffic API endpoint `/repos/:owner/:repo/traffic/clones`.
- The workflow passes `GH_TOKEN: ${{ secrets.TRAFFIC_PAT }}` to the script `.github/scripts/update_clone_stats.py`. A 401 means the token is missing, invalid, expired, or lacks the required scopes.

---

## Immediate recommended actions

1. Verify or (re)create the secret `TRAFFIC_PAT` in repository Settings → Secrets and variables → Actions.
   - Create a Personal Access Token (PAT) with the `repo` scope (safe for private repos; `public_repo` may be insufficient for some traffic endpoints).
   - Add the PAT value as `TRAFFIC_PAT` (do not paste the token into logs or code).

2. Add a short validation step in the workflow to fail early with a clear message if `TRAFFIC_PAT` is missing (example below).

3. Replace the script with the improved version below which:
   - Detects token robustly (GH_TOKEN → TRAFFIC_PAT → GITHUB_TOKEN fallback),
   - Uses the Authorization header format accepted by GitHub,
   - Prints helpful diagnostics on HTTP errors (response body) without exposing the token.

---

## Workflow: validation snippet

Add this step right before the step that runs the Python script in `.github/workflows/clone-count.yml`.

```yaml
- name: Validate TRAFFIC_PAT secret
  env:
    TRAFFIC_PAT: ${{ secrets.TRAFFIC_PAT }}
  run: |
    if [ -z "$TRAFFIC_PAT" ]; then
      echo "ERROR: secrets.TRAFFIC_PAT is not set. Please add the PAT to repository secrets (repo Settings → Secrets → Actions)."
      exit 1
    fi
```

This will fail the job early with a clear error if the secret is missing and avoid the confusing 401 trace.

---

## Python script: improved `.github/scripts/update_clone_stats.py`

Replace the existing script with the following file. It adds robust token handling and better diagnostics for API errors.

```python
#!/usr/bin/env python3
"""GitHub Traffic API'dan klon statistikasini yig'ib, badge + o'sish grafigini yangilaydi."""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.error import HTTPError, URLError

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
            # Use the token format accepted by GitHub API
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "update-clone-stats-action",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        # Try to print the response body for diagnostics (won't reveal the token)
        body = None
        try:
            body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            body = None
        print(f"ERROR: HTTPError {e.code} when requesting {url}: {e.reason}")
        if body:
            print("Response body (for diagnostics):")
            print(body)
        raise
    except URLError as e:
        print(f"ERROR: URLError when requesting {url}: {e.reason}")
        raise


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"total": 0, "lastDate": "1970-01-01", "history": []}


def update_state(state: dict, traffic: dict) -> dict:
    last_date = state.get("lastDate", "1970-01-01")
    total = state.get("total", 0)
    clones_by_date: dict[str, int] = {}
    for entry in traffic.get("clones", []):
        day = entry["timestamp"][:10]
        clones_by_date[day] = clones_by_date.get(day, 0) + int(entry["count"]) 

    history = state.get("history", [])
    history_by_date = {row["date"]: row for row in history}
    if not history_by_date and clones_by_date:
        old_days = [day for day in sorted(clones_by_date) if day <= last_date]
        running_total = total - sum(clones_by_date[day] for day in old_days)
        for day in old_days:
            running_total += clones_by_date[day]
            history_by_date[day] = {
                "date": day,
                "daily": clones_by_date[day],
                "cumulative": running_total,
            }

    new_last_date = last_date

    for day in sorted(clones_by_date):
        count = clones_by_date[day]
        if day > last_date:
            total += count
            history_by_date[day] = {"date": day, "daily": count, "cumulative": total}
            if day > new_last_date:
                new_last_date = day

    if not history_by_date and total > 0 and last_date != "1970-01-01":
        history_by_date[last_date] = {"date": last_date, "daily": 0, "cumulative": total}

    history = [history_by_date[d] for d in sorted(history_by_date)][-HISTORY_LIMIT:]
    return {"total": total, "lastDate": new_last_date, "history": history}


def write_badge(total: int) -> None:
    BADGE_FILE.write_text(
        json.dumps(
            {"schemaVersion": 1, "label": "clones", "message": str(total), "color": "blue"},
            ensure_ascii=False,
            indent=2,
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
    repo = os.environ.get("REPO")
    if not repo:
        print("ERROR: REPO environment variable is not set.")
        sys.exit(1)

    # Robust token detection:
    # Prefer GH_TOKEN (set from workflow), fallback to TRAFFIC_PAT, then GITHUB_TOKEN.
    token = os.environ.get("GH_TOKEN") or os.environ.get("TRAFFIC_PAT") or os.environ.get("GITHUB_TOKEN")

    if not token:
        print("ERROR: No GitHub token found (GH_TOKEN / TRAFFIC_PAT / GITHUB_TOKEN).")
        print("Set secrets.TRAFFIC_PAT in repository secrets, or rely on the built-in GITHUB_TOKEN.")
        sys.exit(1)

    state = load_state()
    # Will raise and print useful diagnostics if token is invalid (401 etc)
    traffic = fetch_traffic(repo, token)

    new_state = update_state(state, traffic)
    STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_badge(new_state["total"]) 

    if new_state["history"]:
        update_readme(build_chart_url(new_state["history"]))

    print(f"Umumiy klon soni: {new_state['total']} (oxirgi hisoblangan sana: {new_state['lastDate']})")


if __name__ == "__main__":
    main()
```

---

## Notes and testing

- If you prefer to use the built-in `GITHUB_TOKEN`, you can change the workflow to pass `GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}`. The script above will accept the fallback automatically. Keep in mind the traffic endpoints may still require a PAT with `repo` scope — if you get `401` or `Resource not accessible by integration`, create a PAT.

- To test locally (do not print or paste tokens into public logs):

```bash
TOKEN=ghp_xxx curl -i -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/TeamLider9141/AI_phone_recommender_bot/traffic/clones
```

- The improved script prints API error response bodies (if any) so when you re-run the workflow after updating the script and secret you will see a clearer message if scopes/permissions are incorrect.

---

If you want, I can commit the updated script file for you and/or add the workflow validation step in a new branch — tell me if you want that and whether to commit directly to the default branch or create a PR.
