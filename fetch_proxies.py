#!/usr/bin/env python3
"""Fetch free HTTP proxy lists from public sources, normalize and dedupe.

Reads SOURCES below (same 16 the scanner bot uses), pulls them in parallel,
normalizes every entry to an http://ip:port URL aiohttp can dial, dedupes,
and writes:
    <out>/http_raw.txt    - every unique candidate (untested)
    <out>/sample.txt      - even sample per source (cap SAMPLE_PER_SOURCE)
    <out>/sources.json    - per-source counts + timestamp
"""
import asyncio
import json
import os
import re
import sys
import time
from urllib.parse import quote

import aiohttp

SOURCES = [
    ("MuRongPIG", "https://raw.githubusercontent.com/MuRongPIG/Proxy-Master/main/http.txt", False),
    ("proxyscrape-v2", "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all", False),
    ("zloiuser", "https://raw.githubusercontent.com/zloi-user/hideip.me/master/http.txt", False),
    ("prxchk", "https://raw.githubusercontent.com/prxchk/proxy-list/main/http.txt", False),
    ("sunny9577", "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/proxies.txt", False),
    ("proxy4parsing", "https://www.proxy-list.download/api/v1/get?type=http", False),
    ("proxifly-http", "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/protocols/http/data.txt", False),
    ("proxifly-all", "https://cdn.jsdelivr.net/gh/proxifly/free-proxy-list@main/proxies/all/data.txt", False),
    ("thespeedx", "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt", False),
    ("jetkai", "https://raw.githubusercontent.com/jetkai/proxy-list/main/online-proxies/txt/proxies-http.txt", False),
    ("mmpx12", "https://raw.githubusercontent.com/mmpx12/proxy-list/master/http.txt", False),
    ("clarketm", "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt", False),
    ("vakhov", "https://raw.githubusercontent.com/vakhov/fresh-proxy-list/master/http.txt", False),
    ("monosans", "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt", False),
    ("proxyscrape", "https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all", False),
    ("roosterkid", "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt", False),
    ("shiftytr", "https://raw.githubusercontent.com/shiftytr/proxy-list/master/proxy.txt", False),
    ("geonode", "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&protocols=http", True),
]

FETCH_CONCURRENCY = int(os.environ.get("FETCH_CONCURRENCY", "12"))
FETCH_TIMEOUT = int(os.environ.get("FETCH_TIMEOUT", "25"))
SAMPLE_PER_SOURCE = int(os.environ.get("SAMPLE_PER_SOURCE", "1000"))

_HOSTPORT_RE = re.compile(
    r"^(?P<host>\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)"
    r":(?P<port>\d{1,5})$")


def _norm_proxy(token):
    """Normalize one proxy entry to a URL aiohttp can dial.

    Accepts: ip:port, host:port, host:port:user:pass, user:pass@host:port and
    scheme://user:pass@host:port.
    """
    t = (token or "").strip().strip('"').strip("'")
    if not t:
        return None
    parts = t.split()
    if parts:
        t = parts[0]
    if "://" in t:
        scheme, t = t.split("://", 1)
        scheme = scheme.lower()
        if scheme not in ("http", "https"):
            return None
    else:
        scheme = "http"

    auth = None
    if "@" in t:
        auth, t = t.rsplit("@", 1)
    else:
        bits = t.split(":")
        if len(bits) == 4 and bits[1].isdigit() and bits[0] and bits[2] and bits[3]:
            host, port, user, pw = bits
            t = f"{host}:{port}"
            auth = f"{user}:{pw}"
        elif (len(bits) == 3 and bits[0] and bits[1].isdigit()
                and bits[2] and not bits[2].isdigit()):
            # ip:port:Country style lists (e.g. zloi-user/hideip.me) -
            # trailing non-numeric tag is metadata, not part of the proxy.
            t = f"{bits[0]}:{bits[1]}"

    m = _HOSTPORT_RE.match(t)
    if not m:
        return None
    host, port = m.group("host"), m.group("port")
    if not (0 < int(port) < 65536):
        return None
    if host.startswith("["):
        host = host.strip("[]")

    out = f"{scheme}://"
    if auth:
        user, _, pw = auth.partition(":")
        if not user or not pw:
            return None
        out += f"{quote(user, safe='')}:{quote(pw, safe='')}@"
    return f"{out}{host}:{port}"


def _proxies_from_text(body):
    out = []
    for tok in re.split(r"[\s,;\"'<>]+", body or ""):
        p = _norm_proxy(tok)
        if p:
            out.append(p)
    return out


def _proxies_from_geonode(body):
    out = []
    try:
        for row in json.loads(body or "{}").get("data", []) or []:
            p = _norm_proxy(f"{row.get('ip', '')}:{row.get('port', '')}")
            if p:
                out.append(p)
    except Exception:
        pass
    return out


async def _fetch_all():
    sem = asyncio.Semaphore(FETCH_CONCURRENCY)
    results = {}

    async def one(session, name, url, is_json):
        try:
            async with sem:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=FETCH_TIMEOUT),
                    ssl=False,
                    headers={"User-Agent": "Mozilla/5.0"},
                ) as r:
                    body = await r.text(errors="ignore")
            found = _proxies_from_geonode(body) if is_json else _proxies_from_text(body)
        except Exception:
            found = []
        return name, found

    async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"},
            trust_env=True) as session:
        for name, found in await asyncio.gather(
                *[one(session, n, u, j) for n, u, j in SOURCES],
                return_exceptions=True):
            if isinstance(name, str):
                results[name] = found
                print(f"[fetch] {name:<15} {len(found):>7} entries", flush=True)
    return results


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "proxies"
    os.makedirs(out_dir, exist_ok=True)

    found = asyncio.run(_fetch_all())

    unique = set()
    for plist in found.values():
        unique.update(plist)

    # even sample: every source contributes, huge lists do not dominate
    sample, seen = [], set()
    for name, plist in found.items():
        take = 0
        for p in plist:
            if p in seen:
                continue
            seen.add(p)
            sample.append(p)
            take += 1
            if take >= SAMPLE_PER_SOURCE:
                break

    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(os.path.join(out_dir, "http_raw.txt"), "w") as f:
        f.write("\n".join(sorted(unique)) + "\n")
    with open(os.path.join(out_dir, "sample.txt"), "w") as f:
        f.write("\n".join(sample) + "\n")
    with open(os.path.join(out_dir, "sources.json"), "w") as f:
        json.dump({
            "timestamp": ts,
            "per_source": {n: len(v) for n, v in found.items()},
            "unique": len(unique),
            "sample": len(sample),
        }, f, indent=2)

    print(f"[fetch] unique={len(unique)} sample={len(sample)} -> {out_dir}/")


if __name__ == "__main__":
    main()
