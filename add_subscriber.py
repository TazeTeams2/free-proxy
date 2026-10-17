#!/usr/bin/env python3
"""Add/update a subscriber with day-limited access.

Used by the add-subscriber workflow (owner triggers it from the Actions tab).
Usage: add_subscriber.py <chat_id> <days> [note]
  days > 0 : add/extend access for N days from today (Myanmar time)
  days = 0 : remove the subscriber
"""
import json
import sys
from datetime import datetime, timedelta, timezone

MMT = timezone(timedelta(hours=6, minutes=30))  # Myanmar time


def main():
    if len(sys.argv) < 3:
        print("usage: add_subscriber.py <chat_id> <days> [note]", file=sys.stderr)
        sys.exit(2)
    chat_id = sys.argv[1].strip()
    if not chat_id.isdigit():
        print(f"bad chat_id {chat_id!r}: must be numeric", file=sys.stderr)
        sys.exit(1)
    try:
        days = int(sys.argv[2])
        if days < 0:
            raise ValueError
    except ValueError:
        print(f"bad days {sys.argv[2]!r}: 0 or positive integer", file=sys.stderr)
        sys.exit(1)
    note = sys.argv[3] if len(sys.argv) > 3 else ""

    try:
        subs = json.load(open("subscribers.json"))
    except Exception:
        subs = {}

    if days == 0:
        removed = subs.pop(chat_id, None)
        action = "removed (was present)" if removed else "not found, nothing to do"
    else:
        expiry = (datetime.now(MMT) + timedelta(days=days)).date().isoformat()
        subs[chat_id] = {"expiry": expiry, "note": note}
        action = f"{days} days -> expiry {expiry}" + (f" ({note})" if note else "")

    with open("subscribers.json", "w") as f:
        json.dump(subs, f, indent=2, ensure_ascii=False)
    print(f"subscriber: {action}")


if __name__ == "__main__":
    main()
