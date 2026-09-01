# CLAUDE.md — agent guide for nyc-restaurants

**Purpose.** A personal, noncommercial NYC dining site: a roster of every award-recognised
NYC restaurant (1,420 venues — Michelin, James Beard, NYT Top 100), with NYC Restaurant Week
participation as one nullable column on it. A Python pipeline crawls sources into `data/`,
builds a SQLite DB, and exports JSON payloads that two static pages in `docs/` (GitHub Pages,
deploy-from-branch `/docs` on `main`) render client-side. **Current state: working and stable.**
Summer 2026 season (srw26) ends 2026-09-06. See `HANDOFF.md` for what to do next.

## Commands (verified 2026-09-01, Windows, Python 3.13)

```bash
pip install -r requirements.txt          # pdfplumber, playwright, pytest
python -m pytest -q tests/               # 474 tests, ~20s. A PermissionError in an
                                         # atexit callback after the summary is Windows
                                         # temp-dir noise — exit code is what counts.
python src/export_site_data.py --check --quiet   # validate dashboard payload, writes nothing
python src/export_venues.py --check --quiet      # validate roster payload, writes nothing
python -m http.server 8741 --directory docs      # serve the site; file:// does NOT work
python src/refresh.py                    # FULL weekly refresh: crawls live sites, ~30-60 min,
                                         # rewrites data/ and docs/data/. Run deliberately.
```

`node tools/verify_ui_counts.mjs` checks every UI count vs. what clicking delivers.
Needs Playwright with browsers (`npx playwright install chromium`); not in CI; run after
touching `app.js`/`venues.js`. `python src/diff_report.py` is NOT read-only: it writes
`data/raw/menus/manifest_history.json`, so a second run reports zero menu changes.

## Architecture map (detail: docs/ARCHITECTURE.md)

- `src/config.py` — season constants, paths, 1 req/s HTTP throttle, NYC bounds/ZIP gates, `GOOGLE_PRIOR`.
- `src/refresh.py` — the orchestrator. **Its inline comments are the authoritative pipeline order.**
- `src/fetch_listing.py` / `fetch_details.py` / `download_menus.py` / `parse_menus.py` — crawl → parsed menus.
- `src/build_db.py` — drops and rebuilds `data/processed/restaurant_week.sqlite` from cached raw files.
- `src/build_venues.py` — the roster spine: venue merging + the slug Ledger (`data/venue_slugs.json`).
- `src/resolve_venues.py` — matches award-only venues to Google Places (`--fetch` is billed; default applies cache).
- `src/export_site_data.py` — dashboard payload → `docs/data/seasons/<code>.json` (+ legacy `restaurants.json`).
- `src/export_venues.py` — roster payload → `docs/data/venues.json`.
- `src/diff_report.py` — week-over-week diff; feeds `src/job_summary.py` → GitHub Actions summary.
- `docs/venues.js` + `index.html` — roster page (no third-party origins in CSP; hand-rolled SVG map).
- `docs/app.js` + `restaurant-week.html` — season dashboard (Leaflet/CARTO allowed in CSP, lazy-loaded).
- `.github/workflows/checks.yml` (PR guards) / `refresh.yml` (Mon cron: refresh + commit data).

## Conventions and gotchas

- **Never hand-edit** anything in `docs/data/` or `data/` — all generated. Hand-maintained inputs
  live in `config/` only. `data/venue_slugs.json` is an append-only identity ledger: never edit,
  never delete entries, never reuse a slug.
- **`config/season.json` is the only file allowed to carry a season/year.**
  `tests/test_no_hardcoded_season.py` enforces this. Changeover runbook: README "Season changeover".
- **ToS (hard rules):** never commit or host menu PDFs (CI fails the run); published menu text
  ≤5% of a menu or 40 chars (`assert_snippet_budget`); ≤1 request/sec to nyctourism (in `config.py`);
  data is for personal, noncommercial use.
- **Google Places costs money.** `resolve_venues.py --fetch`, `fetch_google_ratings.py`, and
  `places_cli.py add` bill per Text Search (~$32/1000). Always `--dry-run` first; never run
  `--force` casually. Key comes from env `GOOGLE_PLACES_KEY` or gitignored `config/secrets.py`
  — never commit or print it. Without a key, refresh skips ratings (that's normal; CI has no key).
- **Don't Read/Glob large data files into context.** `data/raw/` has ~8,000 JSON files;
  `docs/data/*.json` run 1.2–1.6 MB. Inspect with a targeted `python -c` one-liner instead.
  `.claude/settings.json` denies Read on these paths on purpose.
- **Frontend:** bump the `?v=N` query on any changed `.js`/`.css` reference in both HTML files
  (stale-cache crashes are a solved bug — keep it solved). No `innerHTML` for data — `el()` +
  `textContent`. Every href goes through `isHttpURL()`. Facet counts must be computed with
  `matches(row, exceptFacet)` — counting a facet against its own selection is the most-regressed
  bug in this repo (`tools/verify_ui_counts.mjs` exists because of it).
- **Null means unknown** — never coerce missing data to 0/false, never render absence as a zero.
- Keys starting with `_` in `config/*.json` are comments; loaders skip them.
- `build_db.py` recreates the DB, so `tag_dishes.py` and `enrich_recognition.py` must re-run
  after it (refresh.py already does). Exporters refuse to shrink a payload >20% without
  `--allow-shrink` — that guard has caught real upstream failures; don't bypass it to "make it work".
- Ambiguous matches go to `data/processed/*_review.json` for a human ruling, never to a guess.
- Tests open with a docstring naming the bug they prevent — they are the incident log. Read the
  docstring before "fixing" a test.

## Before you finish any task

1. `python -m pytest -q tests/` — must be 474+ passed, 0 failed.
2. `python src/export_site_data.py --check --quiet && python src/export_venues.py --check --quiet`
3. If you touched `docs/`: bump `?v=N`, reload both pages locally, and run
   `node tools/verify_ui_counts.mjs` if anything feeds a count.
4. `git ls-files | grep -ci "\.pdf$"` must print 0. Never stage `config/secrets.py`.

## Model routing

**Sonnet-safe:** README/docs edits; adding tests that mirror an existing test file's pattern;
curation entries in `config/` (aliases, suppressions, shortlist, verified values — copy an
existing entry's shape); CSS/copy tweaks; running the weekly refresh and committing its output;
fixing a bug that already has a failing test.

**Escalate to Opus:** anything in `build_venues.py` (merging, Ledger), `resolve_venues.py`
match thresholds, `export_site_data.py` scoring/rubric/ToS budget, `parse_menus.py` heuristics,
gap arithmetic (`price_sweep.gaps_for`), the Bayesian prior, the season changeover, and any
change spanning both `app.js` and `venues.js` or both pipeline and frontend.
