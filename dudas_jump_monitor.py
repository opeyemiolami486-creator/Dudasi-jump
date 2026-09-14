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


def load_previous_signature() -> str | None:
    if not STATE_FILE.exists():
        return None
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8")).get("signature")
    except (OSError, json.JSONDecodeError):
        return None


def save_signature(signature: str, board: dict[str, Any]) -> None:
    STATE_FILE.write_text(
        json.dumps(
            {
                "signature": signature,
                "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                "board_key": board.get("key"),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def format_message(board: dict[str, Any]) -> str:
    checked = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        f"Dudas Jump leaderboard changed ({checked})",
        f"Board: {board.get('key', 'unknown')}",
        f"Saved leaderboard players: {board.get('players', len(board['list']))}",
        f"Source: {ENDPOINT}",
        "",
    ]
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
    previous = load_previous_signature()

    while True:
        try:
            board = fetch_board()
            signature = top10_signature(board)
            if previous is None:
                # Establish a baseline without sending a noisy first message.
                previous = signature
                save_signature(signature, board)
                print("Baseline saved")
            elif signature != previous:
                body = format_message(board)
                send_telegram(body)
                previous = signature
                save_signature(signature, board)
                print("Leaderboard changed; Telegram message sent")
            else:
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
