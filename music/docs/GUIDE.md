# Music — how this page is built

**Version 1.0.0 · PolyForm Noncommercial 1.0.0**

An album-wise music index: 15 albums, 151 tracks, linking out to SoundCloud, Suno, Flow Music,
Newgrounds and Freesound. Playback happens on the platform that hosts the audio; this page is the
index.

## What is where

| Path | Purpose |
|---|---|
| `index.html`, `styles.css`, `*.js` | the page — no build step, no dependencies |
| `data/tracks.json` | the manifest the page reads — **generated, do not hand-edit** |
| `sources/seed.json` | the crawled catalogue: profiles, tracks, licences, duplicates, takes |
| `sources/*.links.txt` | the link list per platform, one URL per line |
| `tools/build_manifest.py` | seed + link lists → `data/tracks.json` |
| `.github/workflows/` | rebuild the manifest on push, deploy to Pages |

## Adding a track

1. Put the track link in `sources/<platform>.links.txt`.
2. Re-crawl that platform, or paste the row straight into `sources/seed.json`.
3. Push. `rebuild.yml` regenerates `data/tracks.json` and `deploy.yml` publishes it.

Because the manifest is generated, an edit to `data/tracks.json` is overwritten on the next build.
The two source files are the truth.

## Licensing, per track

The catalogue records each track's licence, and the page states the split — how many are
commercial-use and how many are personal-use only. That distinction is why the manifest carries a
licence field per track rather than one licence for the page: the music is not all under the same
terms, and saying so is the honest version.

## Where the page is published

The live page is served by the hub at <https://drsamonline.github.io/music/>, which carries a copy of
these files. A `publish-check` workflow compares the copy against this repository and names any file
that has drifted, with the copy command — because a silent drift here means the site shows an old
catalogue.

## Licence

PolyForm Noncommercial 1.0.0 for the page. See [LICENSE](../LICENSE).
