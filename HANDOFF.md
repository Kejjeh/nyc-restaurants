# HANDOFF — state of play (2026-09-01)

Read `CLAUDE.md` first. This file says what's done, what's broken, and what to do next.
A bot (`github-actions[bot]`) commits a weekly refresh to `main` every Monday —
**always `git pull` before starting work.**

## Done and working

- Full pipeline (`python src/refresh.py`) end-to-end; 474 tests green; CI green.
- Live site: <https://kejjeh.github.io/nyc-restaurants/> (roster, 1,420 venues incl.
  2006–2024 Michelin back-fill, ~1,941 award records, local SVG map) and
  `/restaurant-week.html` (srw26 dashboard, 636 participants: planner, compare, Leaflet map).
- Weekly cron refresh (Mon 11:00 UTC) that commits data; PR checks incl. payload-staleness guard.
- No code work is mid-stream. Sister repo `Kejjeh/nyc-restaurant-week` is the frozen
  pre-roster season tracker — don't confuse the two.

## Waiting on a human (not code)

- **Review queues are non-empty** — the pipeline is waiting on rulings:
  `data/processed/recognition_review.json` (5 michelin + 8 james_beard + 1 nyt) and
  `data/processed/venue_merge_review.json` (1 confirm, 4 refused, 10
  group_award_parts_unmatched, 77 awards_to_a_person_with_no_room).
  An agent may research and *present* each case; only the human rules. Rulings go in
  `config/venue_aliases.json` (merges) or the award files.
- **Parked issue-#3 design questions:** should the recency factor apply per-source, and
  should `top_honor` be best-ever? Human decisions; implementation is small after.

## Known bugs (none block normal work)

1. **`docs/venues.js:49` — `isHttpURL` accepts bare hostnames.** It passes `location.href` as
   base to `new URL`, so a listing value like `"www.joesbar.com"` resolves relative and renders
   a Book link that 404s into `docs/www.joesbar.com`. `docs/app.js:440` documents the correct
   no-base version. Not XSS (`javascript:`/`data:` still blocked). Repro: any roster row whose
   `rw.reserve` lacks a scheme. Fix = copy app.js's implementation + extend `tests/test_roster_links.py`.
2. **`src/price_sweep.py:38` — `ALREADY_ANALYZED`** is a hardcoded set of srw26 slugs; it goes
   stale at changeover, and it contains `code-red-restaurant-lounge` while
   `config/shortlist.json` has `code-red-restaurant-and-lounge` — one of the two is wrong.
3. **`src/build_db.py:163`** hardcodes `swept_date = "2026-08-01"` when reloading the sweep cache.
4. **`src/fetch_google_ratings.py:57-60`** — `from secrets import GOOGLE_PLACES_KEY` shadows the
   stdlib `secrets` module and a bare `except Exception` makes any error in `config/secrets.py`
   read as "no key".
5. Fixed on this branch (`7b6ab40`): `diff_report.previous_payload()` crashed on Windows/cp1252
   (missing `encoding="utf-8"` on `git show`); 2 tests failed there. Suite now 474-green on Windows.
6. Windows pytest prints a `PermissionError` in an atexit callback after the summary — cosmetic,
   exit code unaffected.

## Prioritized next steps

**P0 — merge this branch** (`prep/handoff-20260901`) after human review.
Accept when: checks.yml green; suite green on Windows too.

**P0 — season close-out (time-boxed: Sep 5–6, 2026).** README "Automation" (~line 575) plans a
final refresh once extensions end Sep 6, then pausing the Monday cron.
Steps: on Sep 5 or 6 run the Weekly refresh workflow (or `/weekly-refresh` locally), commit;
then disable the `schedule` trigger in `.github/workflows/refresh.yml` (comment it out, keep
`workflow_dispatch`). Accept when: final data committed; cron disabled; both pages load and show
the season as ended (`seasonPhase()` flips to archive by dates alone — verify, don't assume).
Note: GitHub auto-disables the cron after 60 days of repo inactivity anyway.

**P1 — fix `isHttpURL` in venues.js** (bug 1). One function + one test + bump `?v=`.
Accept when: bare-hostname URLs are dropped on the roster page, new test passes, suite green.

**P1 — present the review queues to the human** (one session: read both files, research each
pending record, write a short recommendation per record; make NO ruling).
Accept when: a markdown summary the human can approve line-by-line.

**P1 — winter 2027 changeover (when announced, ~Dec/Jan).** Follow README "Season changeover
(winter 2027)" exactly — it is a 9-step ordered runbook. Fix bug 2 as part of it. Escalate to
Opus. Accept when: new `config/season.json`; listing validates; new `docs/data/seasons/<code>.json`
exists; srw26 archive entry untouched; suite green.

**P2 — retire the legacy payload.** `docs/data/restaurants.json` is a byte-identical copy of
`seasons/srw26.json`, written at `src/export_site_data.py:1589` (marked TEMPORARY) and read only
by the `LEGACY_URL` fallback in `app.js`. Drop the write and the fallback together, in one change.
Accept when: dashboard still boots with the file deleted, and a `seasons.json` 404 shows the
actionable error message instead of silently falling back.

**P2 — small fixes:** bugs 3 and 4; add an `$opt`-style guard to `venues.js` (a cached
`index.html` against fresh JS currently renders nothing).

**P2 — wire `tools/verify_ui_counts.mjs` into CI** (needs Playwright + browser in the runner).
Accept when: checks.yml runs it headless and green.

## Open questions (need the owner, not an agent)

- **`GOOGLE_PLACES_KEY` in CI?** Ratings fetch is skipped in Actions (no secret wired). Either
  add a restricted key as an Actions secret or keep the fetch local-only. README flags this;
  no decision recorded. Until decided: run rating fetches locally (`/places-fetch`).
- **Is the local Places key restricted & unrotated?** `config/secrets.py` (gitignored) holds a
  key. Confirm in Cloud Console it's restricted to the Places API; rotate if it ever left this
  machine. (Never commit, print, or copy it.)
- **Pause vs. delete the cron** after Sep 6 (P0 assumes pause/comment-out).
- **Doc placement:** the prep spec asked for `docs/ARCHITECTURE.md` / `docs/DECISIONS.md`, but
  `docs/` is the published Pages site, so they sit at repo root instead. Confirm or move.
- **The two parked issue-#3 questions** (per-source recency; best-ever top_honor).
- Local folder name ("NYC Restaurant Week") doesn't match the repo name (`nyc-restaurants`);
  rename was blocked by a process lock — do it from an external terminal when convenient.
- **Write a winter-2027 value report?** `reports/` holds the summer ones; unclear if once-only.

## Tech debt (known, not urgent)

- `tools/verify_ui_counts.mjs` is slow/flaky (fixed sleeps, O(n²) reloads), needs out-of-tree
  Playwright, runs nowhere automatically — count regressions rely on someone remembering it.
- `data/raw/recognition/james_beard.json` and `nyt100.json` are hand-curated with no fetcher and
  no documented refresh path (only Michelin has `backfill_michelin_stars.py`).
- `data/cache/hours.json` (from `hours_lookup.py`) is written but read by nothing.
- `src/price_rescue.py:20-24` mutates `LD_LIBRARY_PATH` for a defunct sandbox.
- README is 1,455 lines of narrative; heavier stale spots were fixed 2026-09-01 but treat
  CLAUDE.md as the agent entry point and README as the human deep-dive.
- No venv / lockfile; tests run against system Python 3.13. `requirements.txt` is 3 loose pins.
- `data/raw/` is ~427 MB locally; a fresh clone re-downloads ~473 menu PDFs on first refresh
  (~10 min at 1 req/sec) — expected, not a bug.
- Dormant-but-intentional: `config/places.json` is empty so every "My list" branch in `app.js`
  is unreachable; `seasons.json` has one entry so `switchSeason()` can't fire yet. Both come
  alive with data — don't delete them as dead code. `app.js`/`venues.js` are large single files
  by design (no build step) — don't split without a decision.
