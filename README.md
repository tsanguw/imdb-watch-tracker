# IMDb Watchlist Tracker

Reads a manually-exported snapshot of your IMDb watchlist, looks up
streaming availability (TMDb) and a heuristic free-YouTube-movie match, and
writes it all to `data/watchlist.xlsx`. Runs weekly via GitHub Actions, and
can be refreshed on demand.

## Why this reads from a CSV instead of scraping IMDb live

This project originally fetched the watchlist directly from IMDb's page.
That turned out to be blocked by an AWS WAF "Human Verification" challenge
— a CAPTCHA-style control aimed specifically at automated browsers, not
just occasional IP-based bot detection. Defeating that kind of check isn't
something this project does, even against your own public data, so there's
no way to pull the watchlist programmatically at all right now.

Instead, you export your watchlist yourself (a normal, authenticated action
in your own real browser — not scraping) and drop the resulting CSV into
the repo. Everything else — TMDb lookups, YouTube search, the Excel output,
the weekly schedule — is still fully automated; only the watchlist snapshot
itself needs a manual refresh whenever you add or remove titles.

## How it works

1. **`src/watchlist_csv.py`** reads `data/imdb_watchlist_export.csv` (see
   "Exporting your watchlist" below). If the file is missing, empty, or
   missing the columns it expects (IMDb's export format has changed before
   and could again), it raises loudly and exits nonzero rather than writing
   an empty/partial result.
2. **`src/tmdb_client.py`** matches each title to TMDb strictly by IMDb ID
   (never by name), then pulls US watch-provider data, split into
   subscription / rent-buy / free ad-supported.
3. **`src/youtube_client.py`** does a best-effort search for a free,
   ad-supported upload from a curated allowlist of official channels
   (`config/youtube_channels.json`). The YouTube API has no "free with ads"
   flag, so this is always labeled unverified in the output — check
   manually before trusting it.
4. **`src/excel_writer.py`** overwrites `data/watchlist.xlsx` with one row
   per title: Title, Year, Subscription Services, Rent/Buy, Free
   (Ad-Supported), Free (YouTube - Unverified), Last Checked. Titles with no
   TMDb match at all show "Not found" instead of being skipped.

## One-time setup

### 0. Install the local commit safeguard (recommended)

```bash
bash scripts/install-git-hooks.sh
```

This installs a pre-commit hook (from `githooks/pre-commit`, since Git
doesn't version `.git/hooks` itself) that blocks any commit which stages
`.env` or contains a hardcoded key/token/secret-shaped string. It's a local
safeguard only — re-run this once after every fresh clone.

### 1. TMDb API key

1. Create an account at [themoviedb.org](https://www.themoviedb.org/).
2. Settings → API → Create → choose "Developer", fill in the short form
   (personal/non-commercial use). For "Application URL" you can use this
   repo's URL.
3. Copy the **API Key (v3 auth)** — not the longer v4 Read Access Token.

### 2. YouTube Data API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and
   create a new project (e.g. "imdb-watch-tracker").
2. APIs & Services → Library → enable **YouTube Data API v3**.
3. APIs & Services → Credentials → Create Credentials → API key → restrict
   it to "YouTube Data API v3" (skip IP restriction — GitHub Actions
   runners don't have stable IPs).
4. Note: `search.list` costs 100 quota units per call against a default
   10,000/day budget (~100 searches/day). The pipeline skips the YouTube
   search for any title that already has a confirmed free ad-supported
   option from TMDb, to conserve this.

### 3. Exporting your watchlist

1. While signed in to IMDb, open your Watchlist.
2. Use the list's **Export** option (in the "..." / options menu) to
   download a CSV.
3. Save it to `data/imdb_watchlist_export.csv` in this repo (overwrite
   the previous export each time).
4. Commit and push it whenever you add/remove titles — the weekly job just
   reads whatever's currently checked in, it doesn't fetch a fresh copy
   itself.

This project expects at least these columns in that CSV: `Const` (the IMDb
ID, e.g. `tt0110912`), `Title`, and `Title Type`. If IMDb has changed its
export format since this was written, the very first run will fail with a
clear error listing the columns it actually found — update
`REQUIRED_COLUMNS` in `src/watchlist_csv.py` to match if so.

### 4. GitHub repo secrets

In your GitHub repo: **Settings → Secrets and variables → Actions → Secrets**, add:

- `TMDB_API_KEY`
- `YOUTUBE_API_KEY`

No extra setup needed for committing the result back to the repo — the
workflow uses the built-in `GITHUB_TOKEN` with `permissions: contents:
write` (already set in `.github/workflows/update.yml`).

### 5. Fill in the YouTube channel allowlist (optional but recommended)

Edit `config/youtube_channels.json` and fill in `channel_id` for whichever
official channels you want checked (Tubi, Popcornflix, FilmRise, Crackle,
studio channels, etc). To find a channel's ID: open the channel → About →
Share channel → Copy channel ID. Entries left blank are skipped, and if
none are filled in, the YouTube column will just always be empty — the
pipeline still runs fine either way.

## Refreshing the tracker

**Scheduled**: runs automatically every Monday at 13:00 UTC via
`.github/workflows/update.yml`, reprocessing whatever watchlist CSV is
currently in the repo and committing the updated `data/watchlist.xlsx`
back. Useful even without a fresh export, since streaming availability for
titles already on your list can change week to week. If a run fails,
GitHub will show it as a failed Actions run (and, depending on your
notification settings, email you) — nothing fails silently.

**On demand, from GitHub**: the same workflow also has a
`workflow_dispatch` trigger:

- From the repo's **Actions** tab → "Update Watchlist" → **Run workflow**
  (optionally check "force_youtube_recheck" to re-check YouTube even for
  titles that already have a free ad-supported hit elsewhere).
- Or from a terminal with the [GitHub CLI](https://cli.github.com/):

  ```bash
  gh workflow run update.yml
  ```

- Or from the GitHub mobile app (Actions tab → same workflow → Run).

This uses the exact same code path as the weekly run, so it's exercised
just as often and just as reliably.

**On demand, locally**: for an instant refresh with no GitHub round-trip:

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your TMDB_API_KEY and YOUTUBE_API_KEY
python -m src.main
```

This writes straight to your local `data/watchlist.xlsx`. Commit/push it
yourself if you want that copy to become the repo's official version, or
just leave it local if you're only checking something once. Add
`--force-youtube-recheck` to bypass the free-ad-supported skip logic.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Known limitations

- **Watchlist freshness depends on you re-exporting.** New titles you add
  to your IMDb watchlist won't show up until you re-export the CSV and
  commit it — the weekly/on-demand runs refresh streaming data for
  whatever's already in `data/imdb_watchlist_export.csv`, they don't detect
  watchlist changes on their own.
- **IMDb's CSV export format could change.** `src/watchlist_csv.py` expects
  `Const`, `Title`, and `Title Type` columns; if IMDb changes this, the run
  fails loudly with the columns it actually found rather than silently
  misreading rows.
- **YouTube "free with ads" matches are always heuristic.** There's no
  public API flag for this; matches are channel-allowlist + keyword based
  and labeled "unverified - check manually" for exactly that reason.
- **TMDb's watch-provider data comes from JustWatch.** Their API terms ask
  for attribution if you display this data publicly — not a concern for a
  private personal spreadsheet, but worth knowing if you ever share it
  widely.
