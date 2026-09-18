# IMDb Watchlist Tracker

Scrapes your public IMDb watchlist, looks up streaming availability (TMDb)
and a heuristic free-YouTube-movie match, and writes it all to
`data/watchlist.xlsx`. Runs weekly via GitHub Actions, and can be refreshed
on demand.

## How it works

1. **`src/imdb_scraper.py`** fetches your public watchlist
   (`https://www.imdb.com/user/<your-id>/watchlist/`) and reads the
   `__NEXT_DATA__` JSON blob IMDb's frontend embeds in the page — a typed
   data structure rather than DOM scraping, but still an undocumented
   internal format. If the expected fields aren't there (IMDb changed
   something, or the watchlist isn't public), it raises loudly and exits
   nonzero instead of writing an empty/partial file.
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
   (personal/non-commercial use).
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

### 3. Your IMDb watchlist

Make sure your watchlist is set to **Public** (IMDb account settings →
General → your Watchlist), and note your IMDb user ID (the `ur1234567`
part of your profile URL).

### 4. GitHub repo secrets and variables

In your GitHub repo: **Settings → Secrets and variables → Actions**

- **Secrets** tab → add:
  - `TMDB_API_KEY`
  - `YOUTUBE_API_KEY`
- **Variables** tab → add:
  - `IMDB_USER_ID` (e.g. `ur1234567`) — not sensitive, so it's a variable
    rather than a secret.

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
`.github/workflows/update.yml`, and commits the updated
`data/watchlist.xlsx` back to the repo. If a run fails, GitHub will show it
as a failed Actions run (and, depending on your notification settings,
email you) — nothing fails silently.

**On demand, from GitHub**: the same workflow also has a
`workflow_dispatch` trigger, so you can run it manually:

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
cp .env.example .env   # fill in your keys and IMDB_USER_ID
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

- **Watchlist pagination past ~100 titles is unverified.** The scraper
  paginates via `?page=N` and cross-checks the collected count against
  IMDb's own reported total, raising an error rather than returning a
  partial list if that assumption turns out to be wrong — but if you have
  a large watchlist, it's worth running once locally to confirm it
  actually pages through everything before relying on the schedule.
- **YouTube "free with ads" matches are always heuristic.** There's no
  public API flag for this; matches are channel-allowlist + keyword based
  and labeled "unverified - check manually" for exactly that reason.
- **TMDb's watch-provider data comes from JustWatch.** Their API terms ask
  for attribution if you display this data publicly — not a concern for a
  private personal spreadsheet, but worth knowing if you ever share it
  widely.
- **Cloud IP bot detection.** GitHub-hosted runners occasionally get
  flagged by IMDb more than a residential IP would. The scraper retries
  the whole fetch once (with a delay) before failing; if blocks become
  persistent, a self-hosted runner or proxy would be the next step (not
  currently implemented).
