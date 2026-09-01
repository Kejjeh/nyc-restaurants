# Architecture

(At repo root, not `docs/`: `docs/` is the published GitHub Pages site — an .md
placed there would become a public web page.)

One-way data flow: crawl → cache → SQLite → JSON payloads → static pages. No backend,
no build step, no framework. Everything the site shows was computed ahead of time in Python;
the browser only filters, sorts, and renders.

## End-to-end flow

```
nyctourism program API ──► fetch_listing.py ──► data/raw/listing/latest.json + dated snapshots
                                │
        ┌───────────────────────┼──────────────────────┐
        ▼                       ▼                      ▼
  fetch_details.py       download_menus.py      (manual side-fetches:
  data/raw/details/      data/raw/menus/*.pdf    fetch_subway, fetch_outdoor_dining,
                         (gitignored!) +         fetch_borough_outlines,
                         manifest.json           backfill_michelin_stars,
                                │                price_sweep/price_rescue,
                                ▼                menu_term_sweep)
                         parse_menus.py ──► data/raw/menus/parsed.json
                                │
                                ▼
                         build_db.py  ── DROPS & REBUILDS ──► data/processed/restaurant_week.sqlite
                                │                             (restaurants, menus, menu_items, price_sweep)
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
  tag_dishes.py          enrich_recognition.py    fetch_google_ratings.py   (needs GOOGLE_PLACES_KEY,
  → menu_item_tags       → recognition table      → data/raw/google/         else skipped)
                                │
                                ▼
                         build_venues.py ──► venues (~1,420) + venue_awards (~1,941) tables,
                                │            data/venue_slugs.json (ledger)
                                ▼
                         resolve_venues.py ──► applies data/raw/venues_google/ cache onto venues
                                │              (offline by default; --fetch is the billed step)
              ┌─────────────────┴───────────────────┐
              ▼                                     ▼
      export_venues.py                       export_site_data.py ──► docs/data/seasons/srw26.json
      → docs/data/venues.json                                        docs/data/seasons.json (registry)
                                                    │                docs/data/restaurants.json (LEGACY copy)
                                                    ▼
                                             export_places.py ──► docs/data/places.json (currently empty)
                                                    ▼
                                             diff_report.py  (week-over-week diff; writes
                                                              data/raw/menus/manifest_history.json)
```

`src/refresh.py` runs exactly this chain in order; its inline comments state which ordering
constraints are load-bearing. `diff_report.py` runs last: the listing half compares the two
latest snapshots, the roster half compares `docs/data/venues.json` against `git show HEAD:`
(no sidecar file), and it prints the human-owed review queues. `src/job_summary.py`
(workflow-only) turns `refresh.log` into the GitHub Actions step summary.

## The two pages

- `index.html` + `venues.js` — the **roster** (1,420 venues, `venues.json`). CSP allows **no
  third-party origin**, which is why its map is hand-rolled SVG over committed borough outlines
  (`boroughs.json`), not Leaflet.
- `restaurant-week.html` + `app.js` — the **season dashboard** (636 participants). Loads
  `seasons.json` (registry) → `seasons/<code>.json`; falls back to legacy `restaurants.json` if
  the registry 404s. CSP additionally allows unpkg (Leaflet 1.9.4) and CARTO tiles, both
  lazy-loaded on first map open.
- Join is by slug: roster rows with `rw.slug` deep-link to `restaurant-week.html#r=<slug>`.

## Key abstractions

- **Venue vs. participant.** The `venues` roster is the universe and the spine; an award is a
  durable fact attached to a venue; Restaurant Week participation is one season's nullable
  attribute (`rw_slug`). `build_venues.py` rebuilds the roster from scratch each run.
- **The slug Ledger** (`data/venue_slugs.json`, `build_venues.Ledger`) makes `venue_slug` a
  durable identity across rebuilds. Reuse is decided on address evidence (street-number /
  ZIP fit score), never on name alone; entries are never deleted; a slug is never reissued to a
  different restaurant; merged venues carry `merged_into`.
- **Merge with asymmetric costs.** A false merge destroys data invisibly; a missed merge is a
  visible duplicate. So merging demands corroboration, string similarity may suggest but never
  decide, and undecidable pairs go to `data/processed/venue_merge_review.json` for a human
  ruling recorded permanently in `config/venue_aliases.json`.
- **Seasons registry.** One payload per season under `docs/data/seasons/`, indexed by
  `seasons.json`. `update_registry()` only touches its own season's entry, so a new season's
  build cannot rewrite an archive. `config/season.json` is the single changeover file.
- **Evidence precedence.** Own printed materials (`config/verified_values.json`) > listing API >
  `price_sweep` heuristics (triage only, may never populate a "verified" field; estimates render
  second-class everywhere). One gap definition lives in `price_sweep.gaps_for()`.
- **Bayesian rating shrinkage.** `GOOGLE_PRIOR = 150` in `config.py` — one definition because
  three payloads publish scores from it and the frontend reads it from the payload.
- **Guards over cleverness.** Fetchers refuse to overwrite good data with a suspicious crawl;
  exporters `--check` their own payloads and refuse >20% shrink; CI re-derives `venues.json`
  and fails on drift.

## Boundaries a change is likely to cross

- **DB schema / payload field** → both exporters → both payloads → both JS pages →
  `tests/test_published_invariants.py` plus the roster/facet tests. `export_places.py` imports
  helpers from `export_site_data.py`, so a change there crosses both payloads.
- **Anything scored or counted** → the exporter computes it, the page only displays it. Fix
  numbers in Python, not JS. UI counts are additionally guarded only by the manual
  `tools/verify_ui_counts.mjs` run (the except-own-facet invariant in `matches()`).
- **Award files or merge rules** → `build_venues` → review-queue contents → `diff_report`.
- **CSP** → adding any external resource to `index.html` is an architecture change (the roster
  page's no-third-party rule is deliberate and tested in `tests/test_roster_map.py`).
- **Season changeover touches ONLY `config/season.json`** (plus new snapshots); everything else
  derives. If a changeover seems to need edits elsewhere, that's a bug — see README
  "Season changeover". `tests/test_no_hardcoded_season.py` enforces it.

## Why it's structured this way

- Static-only because it's a personal tool on GitHub Pages: publishing = committing to `main`.
  CI therefore guards that committed payloads are fresh (rebuilds and diffs them on every PR).
- Raw caches are committed (except PDFs — ToS) so the pipeline is re-runnable and diffable
  without re-crawling, and so CI can rebuild payloads offline.
- The DB is disposable; the raw caches and the ledger are the durable state.
