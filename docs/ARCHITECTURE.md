# Architecture

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
                         (gitignored) +          fetch_borough_outlines,
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
                         build_venues.py ──► venues + venue_awards tables, data/venue_slugs.json (ledger)
                                ▼
                         resolve_venues.py ──► applies data/raw/venues_google/ cache onto venues
                                │
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
constraints are load-bearing. `src/job_summary.py` (workflow-only) turns `refresh.log` into
the GitHub Actions step summary.

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

- **The venue roster is the spine; Restaurant Week is a nullable column.** `build_venues.py`
  rebuilds the roster from scratch each run from award data + the current RW listing.
- **The slug Ledger** (`data/venue_slugs.json`, `build_venues.Ledger`) makes `venue_slug` a
  durable identity across rebuilds. Reuse is decided on address evidence (street-number /
  ZIP fit score), never on name alone; entries are never deleted; a slug is never reissued to a
  different restaurant; merged venues carry `merged_into`.
- **Seasons registry.** One payload per season under `docs/data/seasons/`, indexed by
  `seasons.json`. `update_registry()` only touches its own season's entry, so a new season's
  build cannot rewrite an archive. `config/season.json` is the single changeover file.
- **Evidence precedence.** Own printed materials (`config/verified_values.json`) > listing API >
  `price_sweep` heuristics (triage only, may never populate a "verified" field). One gap
  definition lives in `price_sweep.gaps_for()`; a published gap must be the difference of the
  two published numbers.
- **Bayesian rating shrinkage.** `GOOGLE_PRIOR = 150` in `config.py` — one definition because
  three payloads publish scores from it and the frontend reads it from the payload.
- **Ambiguity → human review files** (`data/processed/recognition_review.json`,
  `venue_merge_review.json`), surfaced weekly by `diff_report.py`. Rulings are recorded in
  `config/venue_aliases.json` / `config/recognition_suppress.json`.

## Boundaries a change is likely to cross

- **Payload shape** → touches an exporter, its `--check` validator, `tests/test_published_invariants.py`,
  and whichever page reads the field. `export_places.py` imports helpers from `export_site_data.py`
  so places and participants share one row shape — a change there crosses both payloads.
- **Anything scored or counted** → the exporter computes it, the page only displays it. Fix
  numbers in Python, not JS.
- **UI counts** → the except-own-facet invariant in `matches()`, verified only by the manual
  `tools/verify_ui_counts.mjs` run.
- **CSP** → adding any external resource to `index.html` is an architecture change (the roster
  page's no-third-party rule is deliberate and tested in `tests/test_roster_map.py`).
- **Season fields** → `config/season.json` → `config.py` constants → both exporters → both pages'
  phase logic (`seasonPhase()`), plus `tests/test_no_hardcoded_season.py`.

## Why it's structured this way

- Static-only because it's a personal tool on GitHub Pages: publishing = committing to `main`.
  CI therefore guards that committed payloads are fresh (rebuilds and diffs them on every PR).
- Raw caches are committed (except PDFs) so the pipeline is re-runnable and diffable without
  re-crawling, and so CI can rebuild payloads offline.
- The DB is disposable; the raw caches and the ledger are the durable state.
