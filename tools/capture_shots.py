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

Invalidation (why a shot is re-captured)
----------------------------------------
A thumbnail is re-captured when **either** of these holds:

1. **Age** — the manifest records a *successful* capture older than
   ``MAX_AGE_DAYS``.
2. **Source changed** — the repo's current ``pushed`` timestamp (from
   ``repos.json``) is newer than the ``source_pushed`` timestamp recorded in the
   manifest when the shot was last taken. This means the landing page's source
   has moved on since the shot, so the image is stale even if it is minutes old.

The manifest stores, per shot, the ``source_pushed`` value seen at capture time
so the comparison is exact. When ``repos.json`` is missing or a project has no
``pushed`` value the source check is simply unavailable and the age check alone
decides — the run never crashes over it.

Placeholders (from a previous failure) are always retried. Passing ``--force``
(or setting ``FORCE_CAPTURE=1``) ignores both checks and re-captures everything.

A capture that fails or times out falls back to a branded placeholder via
``tools/placeholders.py`` so every card always has a local image, and the repo
is retried on the next run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import TimeoutError as PWTimeout  # noqa: E402

from placeholders import make_placeholder  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "assets", "shots")
MANIFEST = os.path.join(SHOTS, "_manifest.json")

VIEWPORT = {"width": 1200, "height": 750}
OUT_SIZE = (600, 375)
MAX_AGE_DAYS = 3
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


def _parse_iso(ts: str | None):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def is_recent_ok(entry: dict | None) -> bool:
    """Age check only: a successful capture newer than ``MAX_AGE_DAYS``."""
    if not entry or entry.get("status") != "ok":
        return False
    when = _parse_iso(entry.get("captured"))
    if when is None:
        return False
    age = (datetime.now(timezone.utc) - when).total_seconds() / 86400
    return age < MAX_AGE_DAYS


def source_changed(entry: dict | None, pushed: str | None) -> bool:
    """True when the repo's current ``pushed`` is newer than the stored one.

    Falls back to a plain inequality when either value is not a parseable
    timestamp, and returns ``False`` (age check decides) when the current
    ``pushed`` is unknown. A missing stored ``source_pushed`` counts as changed
    — we have no record of what source the shot was taken from.
    """
    if not pushed:
        return False
    stored = entry.get("source_pushed") if entry else None
    if not stored:
        return True
    cur, old = _parse_iso(pushed), _parse_iso(stored)
    if cur is None or old is None:
        return pushed != stored
    return cur > old


def needs_capture(entry: dict | None, pushed: str | None, exists: bool) -> bool:
    """Decide whether a shot must be re-taken.

    Re-capture when the file is missing, the last capture was not successful,
    the source has changed, or the capture is older than ``MAX_AGE_DAYS``.
    """
    if not exists:
        return True
    if not entry or entry.get("status") != "ok":
        return True
    if source_changed(entry, pushed):
        return True
    if not is_recent_ok(entry):
        return True
    return False


def capture(page, url: str) -> Image.Image:
    page.set_viewport_size(VIEWPORT)
    try:
        page.goto(url, wait_until="load", timeout=NAV_TIMEOUT_MS)
    except PWTimeout:
        # Some landing pages never fire `load` (streaming assets, long-polling,
        # a camera-permission prompt). The DOM is usually rendered by now, so we
        # still take the shot rather than discarding a perfectly good page.
        # A genuine navigation failure (DNS, TLS, connection refused) is *not*
        # a timeout and propagates, so it still becomes a placeholder.
        pass
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="re-capture every shot, ignoring manifest freshness")
    args = parser.parse_args()
    force = args.force or os.environ.get("FORCE_CAPTURE", "").strip().lower() in {"1", "true", "yes", "on"}

    repos_path = os.path.join(ROOT, "repos.json")
    records = None
    try:
        if os.path.exists(repos_path):
            with open(repos_path, encoding="utf-8") as fh:
                records = (json.load(fh) or {}).get("repos")
    except Exception as exc:  # noqa: BLE001 - a bad repos.json must not kill the run
        print(f"WARN: could not read repos.json ({type(exc).__name__}: {exc}) — "
              f"falling back to age-only")
        records = None

    os.makedirs(SHOTS, exist_ok=True)
    manifest = load_manifest()
    shots = manifest.setdefault("shots", {})

    if not records:
        # No project data (missing/unreadable repos.json): fall back to whatever
        # the manifest already knows so the age check still runs. No source
        # timestamps are available here, so this is age-only — and never crashes.
        print("WARN: repos.json unavailable — falling back to manifest entries (age-only)")
        records = [{"name": name, "landing": e.get("source"), "pushed": None}
                   for name, e in shots.items() if e.get("source")]
        if not records:
            print("nothing to do: no repos.json and no usable manifest entries")
            return

    todo = []
    for r in records:
        out = os.path.join(SHOTS, r["name"] + ".webp")
        entry = shots.get(r["name"])
        pushed = r.get("pushed") or None
        if force:
            todo.append(r)
            continue
        if not needs_capture(entry, pushed, os.path.exists(out)):
            reason = "recent successful capture"
            if entry and entry.get("source_pushed") == pushed:
                reason = "recent capture, source unchanged"
            print(f"skip  {r['name']}  ({reason})")
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
                pushed = r.get("pushed") or None
                out = os.path.join(SHOTS, name + ".webp")
                try:
                    img = capture(page, url)
                    img.save(out, "WEBP", quality=SHOT_QUALITY, method=6)
                    shots[name] = {
                        "status": "ok",
                        "captured": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
                        "source": url,
                        "source_pushed": pushed,
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
                        "source_pushed": pushed,
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
