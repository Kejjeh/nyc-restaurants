# HANDOFF — state of play (2026-09-01)

Read `CLAUDE.md` first. This file says what's done, what's broken, and what to do next.
A bot (`github-actions[bot]`) commits a weekly refresh to `main` every Monday —
**always `git pull` before starting work.**

## Done and working

- Full pipeline (`python src/refresh.py`) end-to-end; 474 tests green; CI green.
- Roster page (1,420 venues incl. 2006–2024 Michelin back-fill) with local SVG map.
- Dashboard for srw26 (636 participants) with seasons registry, planner, compare, Leaflet map.
- Weekly cron refresh (Mon 11:00 UTC) that commits data; PR checks incl. payload-staleness guard.
- No work is mid-stream: the last feature arc (Michelin back-fill → Places resolution →
  roster map → repo rename) landed complete with a clean tree.

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
5. Windows pytest prints a `PermissionError` in an atexit callback after the summary — cosmetic,
   exit code unaffected (also noted in README).

## Prioritized next steps

**P0 — season close-out (time-boxed: Sep 5–6, 2026).** README "Automation" (~line 571) plans a
final refresh once extensions end Sep 6, then pausing the Monday cron.
Steps: on Sep 5 or 6 run the Weekly refresh workflow (or `python src/refresh.py` locally),
commit; then disable the `schedule` trigger in `.github/workflows/refresh.yml` (comment it out,
keep `workflow_dispatch`). Accept when: final data committed; cron disabled; both pages load and
show the season as ended (`seasonPhase()` → archive after `end`). Note: GitHub auto-disables the
cron after 60 days of repo inactivity anyway — disabling it deliberately is still cleaner.

**P1 — fix `isHttpURL` in venues.js** (bug 1 above). One function + one test + bump `?v=`.
Accept when: bare-hostname URLs are dropped on the roster page, new test passes, suite green.

**P1 — winter 2027 changeover (when the season is announced, ~Dec/Jan).** Follow README
"Season changeover (winter 2027)" step by step — it is a 9-step ordered runbook. Also fix
bug 2 (`ALREADY_ANALYZED`) as part of it. Escalate to Opus. Accept when: new
`config/season.json`, listing validates, new `docs/data/seasons/<code>.json` exists, srw26
archive entry untouched, suite green.

**P2 — retire the legacy payload.** `docs/data/restaurants.json` is a byte-identical copy of
`seasons/srw26.json`, written at `src/export_site_data.py:1589` (marked TEMPORARY) and read only
by the `LEGACY_URL` fallback in `app.js`. Drop the write and the fallback together, in one change.
Accept when: dashboard still boots with the file deleted, and a `seasons.json` 404 shows the
actionable error message instead of silently falling back.

**P2 — small fixes:** bugs 3 and 4 above; add an `$opt`-style guard to `venues.js` (a cached
`index.html` against fresh JS currently renders nothing).

## Open questions (need the owner, not an agent)

- **`GOOGLE_PLACES_KEY` in CI?** Ratings fetch is skipped in Actions (no secret wired). Either
  add a restricted key as an Actions secret or keep the fetch local-only. README flags this;
  no decision recorded. Until decided: run rating fetches locally.
- **Is the local Places key restricted & unrotated?** `config/secrets.py` (gitignored) holds a
  key. Confirm in Cloud Console it's restricted to the Places API; rotate if it ever left this
  machine. (Never commit, print, or copy it.)
- **Pause vs. delete the cron** after Sep 6 (P0 assumes pause/comment-out).
- **`.gitignore` change made in this prep branch:** `.claude/` was fully ignored; it now tracks
  `launch.json`, `settings.json`, and `commands/` so agent tooling survives a fresh clone.
  Revert if you'd rather keep `.claude/` private.
- **Write a winter-2027 value report?** `reports/` holds the summer ones; unclear if that's a
  once-only exercise.

## Tech debt (known, not urgent)

- `tools/verify_ui_counts.mjs` is slow/flaky (fixed sleeps, O(n²) reloads), needs out-of-tree
  Playwright, runs nowhere automatically — count regressions rely on someone remembering it.
- `data/raw/recognition/james_beard.json` and `nyt100.json` are hand-curated with no fetcher and
  no documented refresh path (only Michelin has `backfill_michelin_stars.py`).
- `data/cache/hours.json` (from `hours_lookup.py`) is written but read by nothing.
- `src/price_rescue.py:20-24` mutates `LD_LIBRARY_PATH` for a defunct sandbox.
- README is 1,455 lines of narrative; accurate (numbers refreshed 2026-09-01) but heavy.
  CLAUDE.md is the agent entry point; treat README as the human deep-dive.
- No venv / lockfile; tests run against system Python 3.13. `requirements.txt` is 3 loose pins.
- Dormant-but-intentional: `config/places.json` is empty so every "My list" branch in `app.js`
  is unreachable; `seasons.json` has one entry so `switchSeason()` can't fire yet. Both come
  alive with data — don't delete them as dead code.
