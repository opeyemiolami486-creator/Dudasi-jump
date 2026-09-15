#!/usr/bin/env python3
"""Monitor the public Webcade Dudas Jump leaderboard and send Telegram alerts.

This script is read-only: it fetches the public leaderboard endpoint and never
logs in, connects a wallet, submits scores, or places trades.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ENDPOINT = "https://webcade.fun/api/dudas/board?limit=10&window=today"
STATE_FILE = Path(os.getenv("DUDAS_STATE_FILE", "dudas_jump_state.json"))
INTERVAL_SECONDS = int(os.getenv("DUDAS_INTERVAL_SECONDS", "5"))


def row_key(row: dict[str, Any]) -> str:
    """Identify a saved score version from the public leaderboard fields."""
    values = [row.get(k) for k in ("name", "score", "height", "toads", "secs")]
    return json.dumps(values, separators=(",", ":"), sort_keys=False)


def fetch_board() -> dict[str, Any]:
    response = requests.get(ENDPOINT, timeout=20)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("list"), list):
        raise ValueError("Unexpected leaderboard response")
    return payload


def top10_signature(board: dict[str, Any]) -> str:
    rows = [
        {
            "rank": row.get("rank"),
            "name": row.get("name"),
            "score": row.get("score"),
            "height": row.get("height"),
            "toads": row.get("toads"),
            "secs": row.get("secs"),
        }
        for row in board["list"][:10]
    ]
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_state(signature: str, board: dict[str, Any], observed: dict[str, str]) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "signature": signature,
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "board_key": board.get("key"),
                "observed_scores": observed,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def format_message(board: dict[str, Any], new_rows: list[dict[str, Any]], observed: dict[str, str]) -> str:
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"Dudas Jump leaderboard changed ({checked})",
        f"Board: {board.get('key', 'unknown')}",
        f"Saved leaderboard players: {board.get('players', len(board['list']))}",
        f"Source: {ENDPOINT}",
        "Submission time is not exposed by the public API; times below are first-observed UTC times.",
        "",
    ]
    if new_rows:
        lines.append("Newly observed score(s):")
        for row in new_rows:
            lines.append(
                f"  #{row.get('rank')} {row.get('name')} — score {row.get('score'):,}; "
                f"first observed {observed[row_key(row)]}"
            )
        lines.append("")
    for row in board["list"][:10]:
        lines.append(
            f"#{row.get('rank')} {row.get('name')} — score {row.get('score'):,}; "
            f"height {row.get('height')}m; run {row.get('secs')}s"
        )
    return "\n".join(lines)


def send_telegram(body: str) -> None:
    """Send a message through the official Telegram Bot API."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": body,
        "disable_web_page_preview": True,
    }
    thread_id = os.getenv("TELEGRAM_MESSAGE_THREAD_ID")
    if thread_id:
        payload["message_thread_id"] = int(thread_id)
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def main() -> None:
    print(f"Monitoring {ENDPOINT}")
    print(f"Continuous read-only mode; polling every {INTERVAL_SECONDS} seconds")
    state = load_state()
    previous = state.get("signature")
    observed = state.get("observed_scores") if isinstance(state.get("observed_scores"), dict) else {}

    while True:
        try:
            board = fetch_board()
            signature = top10_signature(board)
            current_rows = board["list"][:10]
            new_rows = []
            checked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for row in current_rows:
                key = row_key(row)
                if key not in observed:
                    observed[key] = checked_at
                    new_rows.append(row)
            if previous is None:
                # Establish a baseline without sending a noisy first message.
                previous = signature
                save_state(signature, board, observed)
                print("Baseline saved")
            elif signature != previous or new_rows:
                body = format_message(board, new_rows, observed)
                send_telegram(body)
                previous = signature
                save_state(signature, board, observed)
                print("Leaderboard changed; Telegram message sent")
            else:
                save_state(signature, board, observed)
                print("No change")
        except Exception as exc:
            # Keep monitoring; transient network/Telegram failures should not stop it.
            print(f"Check failed: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    main()

# Required dependency: requests
# Install with: python3 -m pip install requests
# Telegram environment variables:
#   export TELEGRAM_BOT_TOKEN=token-from-botfather
#   export TELEGRAM_CHAT_ID=-1001234567890
# Optional forum-topic variable:
#   export TELEGRAM_MESSAGE_THREAD_ID=123
# Run: python3 dudas_jump_monitor.py
