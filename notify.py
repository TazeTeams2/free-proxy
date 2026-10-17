#!/usr/bin/env python3
"""Send the proxy refresh notification to the owner + active subscribers.

Reads proxies/stats.json and subscribers.json.
Subscribers past their expiry date are pruned (file rewritten, committed
by the workflow). The owner (TG_CHAT_ID) always receives the message.

subscribers.json format:
    {"<chat_id>": {"expiry": "2026-10-24", "note": "Mg Mg"}}

NOTE: repo Actions logs are public, so this script never prints chat IDs.
"""
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

MMT = timezone(timedelta(hours=6, minutes=30))  # Myanmar time
API = "https://api.telegram.org"


def send(token, chat_id, text):
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(f"{API}/bot{token}/sendMessage", data=data)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.load(r)
        if body.get("ok"):
            return True, ""
        return False, str(body.get("description", "?"))[:100]
    except Exception as e:
        desc = ""
        try:
            desc = json.loads(e.read().decode()).get("description", "")
        except Exception:
            pass
        return False, (desc or str(e))[:100]


def build_message(stats, repo):
    f = stats.get("fetch", {})
    per = f.get("per_source", {})
    alive = sum(1 for v in per.values() if v > 0)
    # SHA-pinned link: immutable, so no CDN edge can ever serve a stale copy.
    sha = os.environ.get("DATA_SHA", "").strip()
    ver = f"@{sha}" if sha else "@main"
    link = f"https://cdn.jsdelivr.net/gh/{repo}{ver}/proxies/http_tested.txt"
    return (
        "🔄 <b>Proxy refresh done</b>\n"
        f"🕐 {stats.get('timestamp')}\n"
        f"📡 Sources alive: {alive}/{len(per)}\n"
        f"📦 Unique fetched: {f.get('unique', '?')}\n"
        f"🧪 Tested: {stats.get('candidates')} → "
        f"✅ Working: <b>{stats.get('working')}</b>\n"
        f"🎯 Portal OK: <b>{stats.get('portal_ok')}</b>\n"
        f"⚡ Fastest: {stats.get('fastest_latency_s')}s\n\n"
        f'🔗 <a href="{link}">proxy list နှိပ်ဖွင့်</a>\n'
        f"⏳ Next update: ~{stats.get('next_update', '?')} "
        f"(every {stats.get('refresh_hours', '?')}h)"
    )


def main():
    token = os.environ.get("TG_BOT_TOKEN", "")
    owner = os.environ.get("TG_CHAT_ID", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not owner:
        print("telegram secrets not set, skipping notify")
        return
    try:
        stats = json.load(open("proxies/stats.json"))
        msg = build_message(stats, repo)
    except Exception as e:
        msg = f"⚠️ proxy refresh finished with errors: {e}"

    try:
        subs = json.load(open("subscribers.json"))
    except Exception:
        subs = {}
    today = datetime.now(MMT).date().isoformat()
    active = {c: i for c, i in subs.items()
              if isinstance(i, dict) and i.get("expiry", "") >= today}
    pruned = len(subs) - len(active)
    if pruned:
        with open("subscribers.json", "w") as f:
            json.dump(active, f, indent=2, ensure_ascii=False)
        print(f"pruned {pruned} expired subscriber(s)")

    sent, failed = 0, 0
    ok, err = send(token, owner, msg)
    print(f"owner: {'ok' if ok else 'FAIL ' + err}")
    sent, failed = sent + ok, failed + (not ok)
    for _cid in active:
        ok, err = send(token, _cid, msg)
        print(f"subscriber: {'ok' if ok else 'FAIL ' + err}")
        sent, failed = sent + ok, failed + (not ok)
    print(f"notify done: {sent} sent, {failed} failed, "
          f"{len(active)} active subscribers")


if __name__ == "__main__":
    main()
