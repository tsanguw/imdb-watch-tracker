# IMDb Watchlist Tracker

Reads a manually-exported snapshot of your IMDb watchlist, looks up
streaming availability (TMDb) and a heuristic free-YouTube-movie match, and
writes it all to an Excel file. Run it on demand whenever you want fresh
data.

This repo is public, but your watchlist and the generated spreadsheet stay
entirely on your own machine — see "Keeping your data local" below.

## Tools & technologies used

**Language & runtime**
- Python 3.11+

**Core libraries**
- [`requests`](https://requests.readthedocs.io/) — HTTP calls to TMDb and YouTube, with retry/backoff built in
- [`openpyxl`](https://openpyxl.readthedocs.io/) — building the `.xlsx` output: tier colors, merged section dividers, embedded poster images, hyperlinks
- [`Pillow`](https://pillow.readthedocs.io/) — resizing poster thumbnails before they're embedded
- [`python-dotenv`](https://github.com/theskumar/python-dotenv) — loading a local `.env` file for development
- [`pytest`](https://docs.pytest.org/) (dev only) — the test suite (`tests/`)

**External APIs**
- [TMDb API](https://developer.themoviedb.org/docs) — matching titles by IMDb ID and pulling US watch-provider data
- [YouTube Data API v3](https://developers.google.com/youtube/v3) — heuristic free-movie search

**Data source**
- IMDb's own **watchlist CSV export** feature — a manual, authenticated export you perform yourself

**Tooling**
- **Git** — plus a custom local pre-commit hook (`githooks/pre-commit`, installed via `scripts/install-git-hooks.sh`) that blocks commits containing `.env` or key-shaped strings

**Built with**
- [Claude Code](https://claude.com/claude-code) (Anthropic) — used interactively throughout to design, build, test, and debug this project

## Keeping your data local

Your watchlist and the generated spreadsheet never leave your machine.
Both live in `data/`, which is gitignored (see `.gitignore`) — they're
never staged, committed, or pushed to this (public) repo. There's no cloud
component at all: no GitHub Actions, no second repo, no scheduled job.
You run it yourself, right after exporting a fresh watchlist.

## How it works

1. **`src/watchlist_csv.py`** reads the watchlist CSV from
   `WATCHLIST_CSV_PATH` (`data/imdb_watchlist_export.csv` by default — see
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
4. **`src/excel_writer.py`** overwrites the file at `OUTPUT_PATH`
   (`data/watchlist.xlsx` by default) with rows grouped into color-coded
   availability tiers (free options first, "Not found" last), each with:
   Title, Year, Subscription Services, Rent/Buy, Free (Ad-Supported), Free
   (YouTube - Unverified), Last Checked. Titles with no TMDb match at all
   show "Not found" instead of being skipped.

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
3. APIs & Services → Credentials → Create Credentials → API key.
4. Note: `search.list` costs 100 quota units per call against a default
   10,000/day budget (~100 searches/day). The pipeline skips the YouTube
   search for any title that already has a confirmed free ad-supported
   option from TMDb, to conserve this.

### 3. Exporting your watchlist

1. While signed in to IMDb, open your Watchlist.
2. Use the list's **Export** option (in the "..." / options menu) to
   download a CSV.
3. Save it as `data/imdb_watchlist_export.csv` in this repo (it's
   gitignored — it never gets committed).
4. Re-export and overwrite that file whenever you want fresh data, then
   run the tracker (below). A run only reprocesses whatever's currently in
   the file, it doesn't fetch a fresh copy of your watchlist itself.

This project expects at least these columns in that CSV: `Const` (the IMDb
ID, e.g. `tt0110912`), `Title`, and `Title Type`. If IMDb has changed its
export format since this was written, the very first run will fail with a
clear error listing the columns it actually found — update
`REQUIRED_COLUMNS` in `src/watchlist_csv.py` to match if so.

### 4. Local environment file

```bash
cp .env.example .env
```

Fill in `TMDB_API_KEY` and `YOUTUBE_API_KEY`. `.env` is gitignored, so
these stay local.

### 5. Fill in the YouTube channel allowlist (optional but recommended)

Edit `config/youtube_channels.json` and fill in `channel_id` for whichever
official channels you want checked (Tubi, Popcornflix, FilmRise, Crackle,
studio channels, etc). To find a channel's ID: open the channel → About →
Share channel → Copy channel ID. Entries left blank are skipped, and if
none are filled in, the YouTube column will just always be empty — the
pipeline still runs fine either way.

## Refreshing the tracker

Export a fresh watchlist CSV (see above), then run:

```bash
pip install -r requirements.txt
python -m src.main
```

This writes to `data/watchlist.xlsx` (close it in Excel first). Add
`--force-youtube-recheck` to bypass the free-ad-supported skip logic.

There's deliberately no scheduled job: the watchlist CSV has to be
exported by hand, so a scheduled run would only re-check the same stale
list.

## Running tests

```bash
pip install -r requirements-dev.txt
pytest
```

## Why this reads from a CSV instead of scraping IMDb live

This project originally fetched the watchlist directly from IMDb's page.
That turned out to be blocked by an AWS WAF "Human Verification" challenge
— a CAPTCHA-style control aimed specifically at automated browsers, not
just occasional IP-based bot detection. Defeating that kind of check isn't
something this project does, even against your own public data, so there's
no way to pull the watchlist programmatically at all right now.

Instead, you export your watchlist yourself (a normal, authenticated action
in your own real browser — not scraping) and save the resulting CSV
locally. Everything else — TMDb lookups, YouTube search, the Excel output —
is automated by the run; only the watchlist snapshot itself needs a manual
export.

## Known limitations

- **Watchlist freshness depends on you re-exporting.** New titles you add
  to your IMDb watchlist won't show up until you re-export the CSV — a
  run reprocesses whatever's already in `data/imdb_watchlist_export.csv`,
  it doesn't detect watchlist changes on its own.
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
