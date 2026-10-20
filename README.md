# drsamonline.github.io

The personal project index for **Dr Sohil Momin**, served by GitHub Pages at
**https://drsamonline.github.io/**.

It is a single static page that reads the **public GitHub API at runtime**, so
every repository appears here automatically — there is nothing to update by hand
when a new project is finished.

## How it works

1. On load, the page calls
   `https://api.github.com/users/drsamonline/repos?per_page=100&sort=updated&type=owner`
   (plus the user endpoint for the profile header).
2. It renders a responsive card per repository with the description, primary
   language (colour-coded), stars, forks, licence, last-updated time, topics and
   buttons to the **code** and, when a repository sets one, its **live demo** or
   **download** page.
3. New repositories appear on the next page load. Renamed ones update themselves.
   Archived repositories are labelled, and forks are hidden by default (there is
   a toggle if any exist).
4. Results are cached in `sessionStorage` for 10 minutes to stay well inside
   GitHub's unauthenticated rate limit (60 requests/hour per visitor).
5. A snapshot of the repositories is **embedded in the page** and is used only if
   the API is unreachable or rate-limited, so the page is never blank.

## Images

Each card's cover image is GitHub's own OpenGraph card for the repository
(`opengraph.githubassets.com`). That means it is generated and kept up to date by
GitHub for free.

To give a project a custom cover, set it on GitHub under
**Settings → Social preview**. If an image is ever unavailable, the card falls
back to a gradient tinted with the repository's language colour.

## Customising

Everything configurable lives in the small block at the top of the inline
`<script>` in `index.html`:

| Setting | Purpose |
|---|---|
| `USER` | The GitHub account to list. |
| `EXCLUDE` | Repository names never to show (this site, `.github`). |
| `FEATURED` | Optional list of names to pin to the top, e.g. `["conqueror-os"]`. |
| `CACHE_TTL` | How long a fetched result is reused, in milliseconds. |

## Privacy

The page has no backend, no analytics and no cookies. It only calls GitHub's
public API, and its Content-Security-Policy restricts network access to that API
and to HTTPS images.

## Local preview

```bash
python3 -m http.server 8080
# then open http://localhost:8080/
```

## License

MIT © 2026 Dr Sohil Momin — this covers the page's code.

The written content shown here (project descriptions, the profile text and any
original prose) belongs to its author and is **© 2026 Dr Sohil Momin, all rights
reserved**. Repository descriptions are pulled from the GitHub API and remain
the property of their respective authors.
