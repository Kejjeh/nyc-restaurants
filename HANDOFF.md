# HANDOFF — state of play (2026-09-17)

Read `CLAUDE.md` first. This file says what's done, what's broken, and what to do next.
A bot (`github-actions[bot]`) commits a weekly refresh to `main` every Monday —
**always `git pull` before starting work.**

## Done and working

- Full pipeline (`python src/refresh.py`) end-to-end; **515 tests green** (474 + 41 on the
  branch below); CI green.
- Live site: <https://kejjeh.github.io/nyc-restaurants/> (roster, 1,420 venues incl.
  2006–2024 Michelin back-fill, ~1,941 award records, local SVG map) and
  `/restaurant-week.html` (srw26 dashboard, 636 participants: planner, compare, Leaflet map).
- PR checks (checks.yml) incl. the payload-staleness guard: green.
- Google Places resolution COMPLETE (see P0 below) — do not re-run the billed fetch.
- **Branch `claude/confident-wright-m8h5rz` is open and unmerged**: season-archive
  honesty, the four known bugs below, a staged cron pause, and
  `DECISION-season-tail.md`. Reviewed, not deployed.
- The weekly cron is NOT working: it has failed every week since Aug 10. The pause is
  STAGED on that branch and is not in effect until it merges. See P0.
- Sister repo `Kejjeh/nyc-restaurant-week` is the frozen
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

## Known bugs

**Fixed on branch `claude/confident-wright-m8h5rz` (2026-09-17), not yet merged:**

1. ~~`docs/venues.js:49` — `isHttpURL` accepts bare hostnames.~~ Fixed: the base
   argument is gone, both pages now carry the identical implementation, and
   `tests/test_roster_links.py` fails if either regains a base.
2. ~~`src/price_sweep.py:38` — `ALREADY_ANALYZED` hardcodes srw26 slugs.~~ Moved to
   `config/price_sweep_done.json`. **THREE entries were wrong, not one**: the
   handoff spotted `code-red-restaurant-lounge`, and the same defect had also hit
   `the-bronx-beer-hall` (real slug `bronx-beer-hall`) and `mae-mae-cafe-plant-shop`
   (`mae-mae-cafe-and-plant-shop`). One cause: slugs typed from restaurant names,
   so `&` was not folded to `and` and a leading `The` was not dropped. All three
   venues were re-crawled on every sweep. `catch-nyc` is left alone — that
   restaurant is genuinely not in the listing, so it is a departure, not a typo.
   Guarded by `tests/test_price_sweep_skiplist.py`, which fails on any entry that
   matches nothing while a near-twin slug is live.
3. ~~`src/build_db.py:163` hardcodes `swept_date`.~~ Fixed: `price_sweep` stamps each
   record with the day it was taken and `build_db` reads it. Records written before
   the stamp read NULL. Nothing consumes the column, so no published number moved.
4. ~~`src/fetch_google_ratings.py:57-60` — stdlib `secrets` shadowing.~~ Fixed:
   `config/secrets.py` is loaded by path under a private module name, `sys.path` is
   untouched, and the four outcomes (no file / unloadable / name missing / present)
   are four messages instead of one. `resolve_venues.py` and `places_cli.py` share
   this loader, so all three billed callers get the fix.
5. Also fixed on that branch: the dashboard claimed a full-season archive over a
   10 August snapshot, and the roster named an ended season in the present tense.
   The roster gained `$opt`, so a cached `index.html` against fresh JS no longer
   renders a blank page.

**Still open:**

6. Fixed earlier (`7b6ab40`): `diff_report.previous_payload()` crashed on
   Windows/cp1252 (missing `encoding="utf-8"` on `git show`).
7. Windows pytest prints a `PermissionError` in an atexit callback after the
   summary — cosmetic, exit code unaffected.

## Prioritized next steps

**P0 — the refresh has failed every week since Aug 10; published season data is
still the Aug 10 snapshot. NEEDS AN OWNER DECISION — see `DECISION-season-tail.md`,
which has the options, the numbers and a recommendation.** Both guards that fired
are working as designed; nothing was committed by any failed run.

| Run | Where it stopped | Numbers |
|---|---|---|
| Aug 10 | succeeded | 636 published (this is what the site still shows) |
| Aug 17 | `export_site_data` | 636 → 459 (72%) |
| Aug 24 | `export_site_data` | 636 → 440 (69%) |
| Aug 31 | `fetch_listing` | 308 unique records vs floor 400 |
| Sep 7 | `export_site_data` | 636 → **406** (64%) |
| Sep 14 | `export_site_data` | 636 → **406** (64%) |

**Corrected 2026-09-17 from the Actions logs — the 2026-09-01 version of this
file got two things wrong, because the September runs had not happened yet:**

* **`min_rows` is NOT blocking.** It fired once, on Aug 31. Both September runs
  cleared the 400 floor. Publishing the tail needs ONE override, `--allow-shrink`,
  not two. Do not lower `min_rows`: it is not in the way, and lowering a floor
  that is not firing only removes cover for the next real collapse.
* **The listing is stable, not draining.** 406 on Sep 7 and 406 again on Sep 14,
  eleven days after the programme closed. The Aug 31 dip to 308 was transient.
  That flatness is unexplained by "the season is ending", and `DECISION-season-tail.md`
  gives a one-request check for whether those 406 rows are still srw26 or a
  winter season starting to populate. **If it is a winter code, `--allow-shrink`
  would publish next season's restaurants under this season's dates.** Answer
  that before touching the flag.

The other thing that makes this not a runbook step: `--allow-shrink` does not
merely drop rows. Every surviving row is re-graded, because the rubric's window
component is measured from `scoring_day()`, which agrees with other post-season
exports but not with a mid-season snapshot. Measured: window component mean
21.7 → 2.1, rubric mean 35.3 → 33.1. The 636-row payload has no second copy.

**The site is no longer misleading while this sits open.** As of the branch
below, the dashboard names the Aug 10 as-of date and the 27-day gap instead of
calling itself a full-season archive, and the roster writes the season in the
past tense. Leaving the decision open now costs coverage, not honesty.

**P0 — season close-out (was time-boxed Sep 5–6, 2026; that window has PASSED).**
Still blocked on the decision above.
README "Automation" (~line 575) plans a final refresh once extensions end Sep 6, then
pausing the Monday cron. Steps once unblocked: run the Weekly refresh workflow (or
`/weekly-refresh` locally) with whatever overrides the decision authorises, commit; then
disable the `schedule` trigger in `.github/workflows/refresh.yml` (comment it out, keep
`workflow_dispatch`). Accept when: final data committed; cron disabled; both pages load and
show the season as ended (`seasonPhase()` flips to archive by dates alone — verify, don't
assume). Note: GitHub auto-disables the cron after 60 days of repo inactivity anyway.

**P1 — present the review queues to the human** (one session: read both files, research each
pending record, write a short recommendation per record; make NO ruling).
Accept when: a markdown summary the human can approve line-by-line.

**P1 — winter 2027 changeover (when announced, ~Dec/Jan).** Follow README "Season changeover
(winter 2027)" exactly — it is a 9-step ordered runbook. Re-enable the `schedule`
trigger in `refresh.yml` as part of it (staged commented-out on the branch above). Escalate to
Opus. Accept when: new `config/season.json`; listing validates; new `docs/data/seasons/<code>.json`
exists; srw26 archive entry untouched; suite green.

**P2 — retire the legacy payload.** `docs/data/restaurants.json` is a byte-identical copy of
`seasons/srw26.json`, written at `src/export_site_data.py:1589` (marked TEMPORARY) and read only
by the `LEGACY_URL` fallback in `app.js`. Drop the write and the fallback together, in one change.
Accept when: dashboard still boots with the file deleted, and a `seasons.json` 404 shows the
actionable error message instead of silently falling back.

**P2 — wire `tools/verify_ui_counts.mjs` into CI** (needs Playwright + browser in the runner).
Accept when: checks.yml runs it headless and green.

## Open questions (need the owner, not an agent)

- **`GOOGLE_PLACES_KEY` in CI?** Ratings fetch is skipped in Actions (no secret wired). Either
  add a restricted key as an Actions secret or keep the fetch local-only. README flags this;
  no decision recorded. Until decided: run rating fetches locally (`/places-fetch`).
  NOTE the venue-resolution half is already paid for and DONE — 789 cached records committed
  in `data/raw/venues_google/`, unresolved 709 → 174, mappable 631 → 1,246, 125 venues found
  permanently closed. `python src/resolve_venues.py --dry-run` now reports **0 venues, $0.00**,
  so there is nothing left to buy. The 174 still unresolved were FETCHED AND REFUSED by
  `judge_no_coords` (no address our side, name similarity < 0.62, or an address that
  disagreed) — they are not un-fetched, and re-running `--fetch` will neither cost nor
  change anything. Resolving them further needs better source addresses, not more API calls.
- **Is the local Places key restricted & unrotated?** `config/secrets.py` (gitignored) holds a
  key. Confirm in Cloud Console it's restricted to the Places API; rotate if it ever left this
  machine. (Never commit, print, or copy it.)
- **Pause vs. delete the cron** after Sep 6. A pause (schedule commented out,
  `workflow_dispatch` kept) is STAGED on branch `claude/confident-wright-m8h5rz`
  for review; merging that branch is what puts it into effect. Nothing was changed
  in GitHub's workflow settings.
- **Doc placement:** the prep spec asked for `docs/ARCHITECTURE.md` / `docs/DECISIONS.md`, but
  `docs/` is the published Pages site, so they sit at repo root instead. Confirm or move.
  `DECISION-season-tail.md` follows the same rule, for the same reason.
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
