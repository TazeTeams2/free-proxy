#!/usr/bin/env python3
"""Test proxy candidates in two stages and write the working list.

Stage 1 (always): neutral connectivity check against a generate_204 URL.
                  Any HTTP status counts as "proxy answers".
Stage 2 (optional, TEST_PORTAL=1): re-test the fastest PORTAL_SAMPLE proxies
                  against the real scan target (Ruijie voucher endpoint).

Reads <out>/sample.txt (written by fetch_proxies.py), writes:
    <out>/http_tested.txt  - working proxies, fastest first (http://ip:port)
    <out>/portal_ok.txt    - subset that also answered the portal (stage 2)
    <out>/stats.json       - counts, timings, per-source info
"""
import asyncio
import json
import os
import sys
import time

import aiohttp

NEUTRAL_URL = "http://connectivitycheck.gstatic.com/generate_204"
PORTAL_URL = "https://portal-as.ruijienetworks.com/api/auth/voucher/?lang=en_US"

TEST_CONCURRENCY = int(os.environ.get("TEST_CONCURRENCY", "250"))
TEST_TIMEOUT = int(os.environ.get("TEST_TIMEOUT", "8"))
PORTAL_SAMPLE = int(os.environ.get("PORTAL_SAMPLE", "200"))
PORTAL_CONCURRENCY = int(os.environ.get("PORTAL_CONCURRENCY", "50"))
PORTAL_TIMEOUT = int(os.environ.get("PORTAL_TIMEOUT", "10"))
TEST_PORTAL = os.environ.get("TEST_PORTAL", "1") == "1"


async def _test_list(proxies, url, concurrency, timeout):
    """Return [(proxy, latency)] for proxies that answered. Sorted by latency."""
    ok, lock, sem = [], asyncio.Lock(), asyncio.Semaphore(concurrency)

    async def one(session, proxy):
        try:
            async with sem:
                start = asyncio.get_event_loop().time()
                async with session.get(
                    url,
                    proxy=proxy,
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False,
                    allow_redirects=False,
                ) as r:
                    await r.read()
                    lat = asyncio.get_event_loop().time() - start
                    async with lock:
                        ok.append((proxy, lat, r.status))
        except Exception:
            pass

    async with aiohttp.ClientSession(
            headers={"User-Agent": "Mozilla/5.0", "Accept-Encoding": "identity"},
            trust_env=True) as session:
        await asyncio.gather(*[one(session, p) for p in proxies],
                             return_exceptions=True)
    ok.sort(key=lambda x: x[1])
    return [(p, lat) for p, lat, _s in ok]


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "proxies"
    with open(os.path.join(out_dir, "sample.txt")) as f:
        candidates = [ln.strip() for ln in f if ln.strip()]
    print(f"[test] candidates: {len(candidates)}", flush=True)

    t0 = time.time()
    working = asyncio.run(_test_list(candidates, NEUTRAL_URL,
                                    TEST_CONCURRENCY, TEST_TIMEOUT))
    t1 = time.time()
    print(f"[test] stage1 working: {len(working)} in {t1 - t0:.1f}s", flush=True)

    with open(os.path.join(out_dir, "http_tested.txt"), "w") as f:
        f.write("\n".join(p for p, _ in working) + "\n")

    portal_ok, t2 = [], t1
    if TEST_PORTAL and working:
        top = [p for p, _ in working[:PORTAL_SAMPLE]]
        print(f"[test] stage2 portal sample: {len(top)}", flush=True)
        portal = asyncio.run(_test_list(top, PORTAL_URL,
                                        PORTAL_CONCURRENCY, PORTAL_TIMEOUT))
        t2 = time.time()
        portal_ok = [p for p, _ in portal]
        print(f"[test] stage2 portal ok: {len(portal_ok)} in {t2 - t1:.1f}s", flush=True)
        with open(os.path.join(out_dir, "portal_ok.txt"), "w") as f:
            f.write("\n".join(portal_ok) + "\n")

    stats = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "candidates": len(candidates),
        "working": len(working),
        "portal_ok": len(portal_ok),
        "stage1_seconds": round(t1 - t0, 1),
        "stage2_seconds": round(t2 - t1, 1),
        "fastest_latency_s": round(working[0][1], 3) if working else None,
    }
    try:
        with open(os.path.join(out_dir, "sources.json")) as f:
            stats["fetch"] = json.load(f)
    except Exception:
        pass
    with open(os.path.join(out_dir, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    print(f"[test] done -> {out_dir}/http_tested.txt ({len(working)} working)")


if __name__ == "__main__":
    main()
