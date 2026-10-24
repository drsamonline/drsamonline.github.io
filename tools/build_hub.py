#!/usr/bin/env python3
"""Build-time data pipeline for the drsamonline.github.io showcase hub.

Runs inside GitHub Actions with the runner's authenticated ``GITHUB_TOKEN``, so
the GitHub API is never subject to the 60-requests/hour *unauthenticated* limit
that broke the old runtime fetch. It is the single place that talks to GitHub.

It produces three committed artefacts:

* ``repos.json``   — the merged project data the page fetches (same origin,
                     no rate limit, cacheable). This is the page's real source.
* ``index.html``   — the embedded offline snapshot and the JSON-LD ItemList are
                     regenerated so they always match ``repos.json``.
* ``sitemap.xml``  — one ``<url>`` per project landing page.

The ``CURATED`` map inside ``index.html`` remains the single source of the
curated fields (category, description, demo/release availability, featured
flags, kicker, tag). A repository that is **not** in the map still appears —
under the automatic ``other`` ("Other / New") category — using its GitHub
description, so a brand-new repo is never silently dropped.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

OWNER = "drsamonline"
SITE = "https://drsamonline.github.io"

# --------------------------------------------------------------------------- #
# What COUNTS as a project — an explicit definition, not an accident of the API
# --------------------------------------------------------------------------- #
# A repository appears on the hub, and in every number the hub shows, only if it
# satisfies this definition. That is what keeps the hub's count and the
# console's count from drifting apart again: both can point at the same rule.
#
#   public     a private repo is never published on a public hub
#   source     a fork is someone else's repo; the origin is the project, not the copy
#   non-empty  a repo with no content (size 0) is a placeholder, not a project
#   not self   the profile (drsamonline) and this site (drsamonline.github.io)
#              are the hub's own scaffolding, not projects
#
# Archived repos are still COUNTED and shown — an archived project is still a
# project; it simply carries an "archived" marker on its card.
EXCLUDE = {"drsamonline", "drsamonline.github.io"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def classify(repos: list[dict]) -> tuple[list[dict], dict]:
    """Split repos into those the definition counts, plus an auditable breakdown.

    Returns ``(counted, breakdown)``. The breakdown is written into repos.json
    so the number is always explainable, and it is printed at build time.
    """
    counted: list[dict] = []
    b = {"total": len(repos), "public": 0, "private": 0, "source": 0, "fork": 0,
         "empty": 0, "archived": 0, "excluded": 0, "counted": 0}
    for r in repos:
        name = r.get("name") or ""
        if not name:
            continue
        key = name.lower()
        private = bool(r.get("private"))
        fork = bool(r.get("fork"))
        empty = int(r.get("size") or 0) == 0
        archived = bool(r.get("archived"))
        b["private" if private else "public"] += 1
        b["fork" if fork else "source"] += 1
        if empty:
            b["empty"] += 1
        if archived:
            b["archived"] += 1
        if private or fork or empty or key in EXCLUDE:
            b["excluded"] += 1
            continue
        counted.append(r)
    b["counted"] = len(counted)
    return counted, b


CAT_LABEL = {
    "desktop": "Desktop & System Tools",
    "games": "Games & Engines",
    "health": "Health & Medicine",
    "mind": "Mind, Memory & Wellbeing",
    "audio": "Audio & Media",
    "business": "Business & Productivity",
    "other": "Other / New",
}
CAT_ORDER = ["desktop", "games", "health", "mind", "audio", "business", "other"]


# --------------------------------------------------------------------------- #
# GitHub API
# --------------------------------------------------------------------------- #
def _token() -> str:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""


def api(path: str):
    url = "https://api.github.com" + path
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "drsamonline-hub-build",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    tok = _token()
    if tok:
        req.add_header("Authorization", "Bearer " + tok)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch_repos() -> list[dict]:
    """Every repo the account owns, following pagination.

    ``HUB_REPOS_FILE`` may point at a cached API response (a list, or an object
    with a ``repos`` key) — used for local runs where the sandbox is behind an
    egress proxy. In Actions the live API is always used.
    """
    local = os.environ.get("HUB_REPOS_FILE")
    if local and os.path.exists(local):
        with open(local, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else data.get("repos", [])

    out: list[dict] = []
    page = 1
    while True:
        batch = api(f"/users/{OWNER}/repos?per_page=100&sort=updated&type=owner&page={page}")
        if not isinstance(batch, list) or not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    return out


# --------------------------------------------------------------------------- #
# index.html helpers
# --------------------------------------------------------------------------- #
def read(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path: str, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def extract_curated(html: str) -> dict:
    """Read the ``var CURATED = {...};`` object out of index.html."""
    m = re.search(r"var\s+CURATED\s*=\s*", html)
    if not m:
        sys.exit("FATAL: could not find `var CURATED` in index.html")
    i = m.end()
    if html[i] != "{":
        sys.exit("FATAL: CURATED is not an object literal")
    depth = 0
    in_str = False
    esc = False
    j = i
    while j < len(html):
        c = html[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                j += 1
                break
        j += 1
    return json.loads(html[i:j])


def replace_block(html: str, start: str, end: str, block: str) -> str:
    pat = re.compile(re.escape(start) + r".*?" + re.escape(end), re.S)
    if not pat.search(html):
        sys.exit(f"FATAL: markers {start} / {end} not found in index.html")
    return pat.sub(lambda _m: block, html, count=1)


def json_in_html(obj) -> str:
    """Compact JSON that is safe to embed inside a <script> element."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def build_records(repos: list[dict], curated: dict) -> list[dict]:
    records: list[dict] = []
    for r in repos:
        name = r.get("name") or ""
        if not name:
            continue
        key = name.lower()
        if r.get("fork") or key in EXCLUDE:
            continue
        c = curated.get(key) or {}
        cat = c.get("cat") or "other"
        if cat not in CAT_LABEL:
            cat = "other"
        landing = (r.get("homepage") or "").strip() or f"{SITE}/{name}/"
        records.append({
            "name": name,
            "key": key,
            "desc": c.get("desc") or (r.get("description") or "").strip() or "A project by Dr. Sohil Momin.",
            "cat": cat,
            "catLabel": CAT_LABEL[cat],
            "demo": bool(c.get("demo")),
            "feat": bool(c.get("feat")),
            "rel": bool(c.get("rel")),
            "kicker": c.get("kicker") or "",
            "tag": c.get("tag") or "",
            "lang": r.get("language") or "",
            "stars": int(r.get("stargazers_count") or 0),
            "pushed": r.get("pushed_at") or "",
            "archived": bool(r.get("archived")),
            "topics": r.get("topics") or [],
            "hasPages": bool(r.get("has_pages")),
            "landing": landing,
            "source": f"https://github.com/{OWNER}/{name}",
            "releases": f"https://github.com/{OWNER}/{name}/releases",
            "shot": f"assets/shots/{name}.webp",
        })
    records.sort(key=lambda x: x["key"])
    return records


def build_jsonld(records: list[dict]) -> dict:
    items = []
    for i, r in enumerate(records, 1):
        items.append({
            "@type": "ListItem",
            "position": i,
            "name": r["name"],
            "url": r["landing"],
            "item": {
                "@type": "SoftwareApplication",
                "name": r["name"],
                "description": r["desc"],
                "applicationCategory": "WebApplication",
                "url": r["landing"],
                "codeRepository": r["source"],
            },
        })
    return {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "Person",
                "@id": f"{SITE}/#person",
                "name": "Dr. Sohil Momin",
                "honorificPrefix": "Dr.",
                "jobTitle": "Homeopathic Physician & Software Builder",
                "description": ("Dr. Sohil Momin, BHMS \u2014 homeopathic physician and builder of "
                                "open-source, offline-first software for medicine, learning and play."),
                "url": f"{SITE}/",
                "sameAs": [f"https://github.com/{OWNER}"],
                "knowsAbout": ["Homeopathy", "Materia Medica", "Offline-first software", "Web games"],
            },
            {
                "@type": "WebSite",
                "@id": f"{SITE}/#website",
                "name": "Dr. Sohil Momin \u2014 Projects",
                "url": f"{SITE}/",
                "description": f"A showcase hub of {len(records)} open-source projects by Dr. Sohil Momin.",
                "publisher": {"@id": f"{SITE}/#person"},
                "inLanguage": "en",
            },
            {
                "@type": "ItemList",
                "name": "Projects by Dr. Sohil Momin",
                "numberOfItems": len(records),
                "itemListElement": items,
            },
        ],
    }


def sync_counts(html: str, records: list[dict]) -> str:
    """Rewrite the hardcoded count labels so the visible TEXT matches the data.

    The page's JS updates the id'd spans at runtime, but the meta description and
    the og/twitter titles are static - and they were drifting (they said "40").
    This keeps every number in step with ``repos.json``.
    """
    n = len(records)
    cats = len({r["cat"] for r in records})
    demos = sum(1 for r in records if r["demo"])
    subs = [
        (r"Explore \d+ projects", "Explore %d projects" % n),
        (r"\u2014 \d+ open-source projects, one hub", "\u2014 %d open-source projects, one hub" % n),
        (r"(\d+) open-source projects", "%d open-source projects" % n),
        (r'(<span id="heroCount">)\d+(</span>)', r"\g<1>%d\g<2>" % n),
        (r'(<span id="projCount">)\d+(</span>)', r"\g<1>%d\g<2>" % n),
        (r'(id="statProjects">)\d+(<)', r"\g<1>%d\g<2>" % n),
        (r'(id="statCats">)\d+(<)', r"\g<1>%d\g<2>" % cats),
        (r'(id="statDemos">)\d+(<)', r"\g<1>%d\g<2>" % demos),
    ]
    for pat, rep in subs:
        html = re.sub(pat, rep, html)
    return html


def build_sitemap(records: list[dict], lastmod: str) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
             f'  <url><loc>{SITE}/</loc><lastmod>{lastmod}</lastmod><changefreq>weekly</changefreq><priority>1.0</priority></url>']
    for r in records:
        lines.append(f'  <url><loc>{r["landing"]}</loc><lastmod>{lastmod}</lastmod>'
                     f'<changefreq>weekly</changefreq><priority>0.7</priority></url>')
    lines.append('</urlset>')
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
def main() -> None:
    index_path = os.path.join(ROOT, "index.html")
    html = read(index_path)
    curated = extract_curated(html)

    counted, breakdown = classify(fetch_repos())
    records = build_records(counted, curated)
    if not records:
        sys.exit("FATAL: no repositories returned by the GitHub API")

    now = datetime.now(timezone.utc).replace(microsecond=0)
    iso = now.isoformat().replace("+00:00", "Z")
    lastmod = now.date().isoformat()

    # 1. repos.json — the page's same-origin data source.
    payload = {"generated_at": iso, "owner": OWNER, "count": len(records),
               "counts": breakdown, "repos": records}
    write(os.path.join(ROOT, "repos.json"),
          json.dumps(payload, ensure_ascii=False, indent=1) + "\n")

    # 2. embedded snapshot — offline fallback, always identical to repos.json.
    html = replace_block(
        html, "<!--REPO_SNAPSHOT_START-->", "<!--REPO_SNAPSHOT_END-->",
        "<!--REPO_SNAPSHOT_START-->\n"
        '<script id="repo-snapshot" type="application/json">' + json_in_html(records) + "</script>\n"
        "<!--REPO_SNAPSHOT_END-->")

    # 3. JSON-LD ItemList — keeps the SEO block in step with the data.
    html = replace_block(
        html, "<!--JSONLD_START-->", "<!--JSONLD_END-->",
        "<!--JSONLD_START-->\n"
        '<script type="application/ld+json">' + json_in_html(build_jsonld(records)) + "</script>\n"
        "<!--JSONLD_END-->")

    # 4. the visible count labels (meta description, og/twitter titles, no-JS fallbacks)
    html = sync_counts(html, records)
    write(index_path, html)

    # 5. sitemap.xml
    write(os.path.join(ROOT, "sitemap.xml"), build_sitemap(records, lastmod))

    print("counted %d of %d repos (%d private, %d forks, %d empty, %d excluded; "
          "%d archived)" % (breakdown["counted"], breakdown["total"], breakdown["private"],
                             breakdown["fork"], breakdown["empty"], breakdown["excluded"],
                             breakdown["archived"]))
    cats = sorted({r["cat"] for r in records})
    print(f"repos.json: {len(records)} projects, {len(cats)} categories "
          f"({', '.join(cats)}), {sum(1 for r in records if r['demo'])} with a live demo")
    missing = [r["key"] for r in records if r["key"] not in curated]
    if missing:
        print("not in CURATED (placed under Other / New):", ", ".join(missing))


if __name__ == "__main__":
    main()
