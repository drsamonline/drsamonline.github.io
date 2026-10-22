# drsamonline.github.io

The personal project index for **Dr Sohil Momin**, served by GitHub Pages at
**https://drsamonline.github.io/**.

[![Live site](https://img.shields.io/badge/live%20site-drsamonline.github.io-2e7d32
[![Projects: 41](https://img.shields.io/badge/projects-41-2e7d32
[![Offline-first](https://img.shields.io/badge/offline--first-yes-2e7d32
[![No trackers, no cookies](https://img.shields.io/badge/no%20trackers-no%20cookies-586069
[![Type: project hub](https://img.shields.io/badge/type-project%20hub-586069

**Live site:** <https://drsamonline.github.io/> &nbsp;·&nbsp; **Source:** <https://github.com/drsamonline/drsamonline.github.io>

A single static page that lists every project. The data is **built ahead of
time and committed**, so the page never depends on a rate-limited third-party
call to render — it fetches one same-origin JSON file and falls back to an
embedded snapshot if that is unavailable.

## How it works

1. A scheduled GitHub Actions workflow (`.github/workflows/refresh-hub.yml`)
   runs daily at 03:17 UTC and on `workflow_dispatch`, with
   `permissions: contents: write`.
2. It calls the GitHub API **with the runner's authenticated token** (never the
   60-requests/hour unauthenticated limit), drops forks and the
   `drsamonline` / `drsamonline.github.io` repos, and merges the rest with the
   `CURATED` map inside `index.html`. A repo that is **not** in the map still
   appears, under the automatic **Other / New** category, using its GitHub
   description.
3. `tools/build_hub.py` writes the merged data to **`repos.json`** and
   regenerates the embedded snapshot in `index.html` (so the offline fallback
   always matches) plus the JSON-LD `ItemList` and `sitemap.xml`.
4. `tools/capture_shots.py` loads every project landing page at 1200×750,
   downscales to 600×375 and encodes **WebP** into `assets/shots/<repo>.webp`.
   Images that already exist, are recent and were a successful capture are
   skipped; failures fall back to a branded placeholder and are retried.
5. Everything is committed back to the repository.

At runtime the page:

* renders instantly from the embedded snapshot, then
* fetches **`repos.json`** (same origin, no rate limit, fast) and re-renders.

No third-party screenshot host, no runtime GitHub API call, no analytics.

## Design

* Calm, professional palette built on CSS custom properties in `:root`, with a
  full override under `[data-theme="dark"]`. Body text meets WCAG AA (4.5:1)
  and UI borders meet 3:1 in both themes.
* A **theme toggle** in the navigation that respects `prefers-color-scheme` on a
  first visit, persists the choice in `localStorage`, applies the stored theme
  **before first paint** via a tiny inline `<head>` script, updates its
  `aria-label` / `aria-pressed` and icon, and works with the keyboard.
* `prefers-reduced-motion` is honoured throughout.
* Self-contained: inline CSS/JS, no external JS libraries, inline SVG icons.

## Layout

| Path | Purpose |
|---|---|
| `index.html` | The hub. Contains the `CURATED` map (source of curated fields) and the embedded snapshot. |
| `repos.json` | Build-time data the page fetches at runtime. |
| `tools/build_hub.py` | Fetches the API, merges with `CURATED`, writes `repos.json` + snapshot + JSON-LD + sitemap. |
| `tools/capture_shots.py` | Captures and encodes the local thumbnails. |
| `tools/placeholders.py` | Branded fallback thumbnail. |
| `assets/shots/` | Locally served thumbnails (`<repo>.webp`) + `_manifest.json`. |
| `.github/workflows/refresh-hub.yml` | The scheduled build. |

## Customising

Everything configurable lives in the small block at the top of the inline
`<script>` in `index.html`:

| Setting | Purpose |
|---|---|
| `CURATED` | Per-repo `cat`, `desc`, `demo`, `feat`, `rel`, `kicker`, `tag`. |
| `CAT_LABEL` / `CAT_ORDER` | Category names and display order. |
| `FEATURED` | Repo keys pinned to the top of the Featured section. |

## Local preview

```bash
python3 -m http.server 8080
# then open http://localhost:8080/
```

To regenerate the data locally without the API:

```bash
HUB_REPOS_FILE=repos_raw.json python3 tools/build_hub.py
```

## Privacy

The page has no backend, no analytics and no cookies. It fetches only its own
`repos.json` and its own images; the Content-Security-Policy restricts network
access to `'self'`.

## License

MIT © 2026 Dr Sohil Momin — this covers the page's code.

The written content shown here (project descriptions, the profile text and any
original prose) belongs to its author and is **© 2026 Dr Sohil Momin, all rights
reserved**. Repository descriptions are pulled from the GitHub API and remain
the property of their respective authors.
