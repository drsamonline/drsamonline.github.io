#!/usr/bin/env python3
"""Capture locally-served WebP thumbnails for every project landing page.

Runs inside GitHub Actions (whose runners can reach ``*.github.io``; the local
dev sandbox cannot). For every project in ``repos.json`` it:

* loads ``https://drsamonline.github.io/<repo>/`` at **1200 x 750**,
* waits for the page to settle,
* downscales to **600 x 375** and encodes **WebP**,
* writes ``assets/shots/<repo>.webp``.

No third-party screenshot host is involved — the bytes are generated here and
committed, so the page serves them from its own origin.

Skip logic: an image is left alone when the manifest records a *successful*
capture for it that is newer than ``MAX_AGE_DAYS`` and the file still exists.
Placeholders (from a previous failure) are always retried.

A capture that fails or times out falls back to a branded placeholder via
``tools/placeholders.py`` so every card always has a local image, and the repo
is retried on the next run.
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime, timezone

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from placeholders import make_placeholder  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "assets", "shots")
MANIFEST = os.path.join(SHOTS, "_manifest.json")

VIEWPORT = {"width": 1200, "height": 750}
OUT_SIZE = (600, 375)
MAX_AGE_DAYS = 14
NAV_TIMEOUT_MS = 25_000
SETTLE_MS = 1_500
SHOT_QUALITY = 76


def load_manifest() -> dict:
    if os.path.exists(MANIFEST):
        try:
            with open(MANIFEST, encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            pass
    return {"generated_at": None, "shots": {}}


def save_manifest(m: dict) -> None:
    m["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(m, fh, ensure_ascii=False, indent=1, sort_keys=True)
        fh.write("\n")


def is_recent_ok(entry: dict | None) -> bool:
    if not entry or entry.get("status") != "ok":
        return False
    ts = entry.get("captured")
    if not ts:
        return False
    try:
        when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return False
    age = (datetime.now(timezone.utc) - when).total_seconds() / 86400
    return age < MAX_AGE_DAYS


def capture(page, url: str) -> Image.Image:
    page.set_viewport_size(VIEWPORT)
    page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
    try:
        page.wait_for_load_state("networkidle", timeout=6_000)
    except Exception:
        pass
    page.wait_for_timeout(SETTLE_MS)
    raw = os.path.join("/tmp", "shot_raw.png")
    page.screenshot(path=raw, clip={"x": 0, "y": 0, **VIEWPORT})
    img = Image.open(raw).convert("RGB")
    return img.resize(OUT_SIZE, Image.LANCZOS)


def main() -> None:
    repos_path = os.path.join(ROOT, "repos.json")
    if not os.path.exists(repos_path):
        sys.exit("FATAL: repos.json not found — run tools/build_hub.py first")
    with open(repos_path, encoding="utf-8") as fh:
        records = json.load(fh)["repos"]

    os.makedirs(SHOTS, exist_ok=True)
    manifest = load_manifest()
    shots = manifest.setdefault("shots", {})

    todo = []
    for r in records:
        out = os.path.join(SHOTS, r["name"] + ".webp")
        if os.path.exists(out) and is_recent_ok(shots.get(r["name"])):
            print(f"skip  {r['name']}  (recent successful capture)")
            continue
        todo.append(r)

    captured = failed = 0
    if todo:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox", "--disable-dev-shm-usage"])
            ctx = browser.new_context(viewport=VIEWPORT, device_scale_factor=1)
            page = ctx.new_page()
            for r in todo:
                name, url = r["name"], r["landing"]
                out = os.path.join(SHOTS, name + ".webp")
                try:
                    img = capture(page, url)
                    img.save(out, "WEBP", quality=SHOT_QUALITY, method=6)
                    shots[name] = {
                        "status": "ok",
                        "captured": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                        "source": url,
                        "bytes": os.path.getsize(out),
                    }
                    captured += 1
                    print(f"ok    {name}  {os.path.getsize(out):>6} B")
                except Exception as exc:  # noqa: BLE001 - one bad page must not stop the run
                    make_placeholder(name, out)
                    shots[name] = {
                        "status": "placeholder",
                        "captured": None,
                        "source": url,
                        "reason": type(exc).__name__,
                        "bytes": os.path.getsize(out),
                    }
                    failed += 1
                    print(f"FAIL  {name}  -> placeholder ({type(exc).__name__})")
            ctx.close()
            browser.close()

    save_manifest(manifest)

    # Report total committed weight (everything under assets/shots).
    total = sum(os.path.getsize(os.path.join(SHOTS, f))
                for f in os.listdir(SHOTS) if f.endswith(".webp"))
    print(f"\ncaptured={captured} placeholder={failed} skipped={len(records) - len(todo)}")
    print(f"assets/shots total: {total} bytes ({total / 1048576:.2f} MB) across "
          f"{sum(1 for f in os.listdir(SHOTS) if f.endswith('.webp'))} images")


if __name__ == "__main__":
    main()
