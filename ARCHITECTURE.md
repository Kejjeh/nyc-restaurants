# Architecture

(At repo root, not `docs/`: `docs/` is the published GitHub Pages site — an .md
placed there would become a public web page.)

## Data flow, end to end

```
nyctourism.com listing ──fetch_listing──▶ data/raw/listing/snapshot-YYYY-MM-DD.json
        │ per-restaurant pages ──fetch_details──▶ data/raw/details/
        │ official menu PDFs ──download_menus──▶ data/raw/menus/*.pdf   (gitignored!)
        │                                            └─parse_menus─▶ structured text
award files (hand-curated + backfill_michelin_stars) ─▶ data/raw/recognition/*.json
city licence register ──fetch_outdoor_dining──▶ data/raw/outdoor/
Google Places (paid, keyed) ──fetch_google_ratings / resolve_venues --fetch──▶ caches

                 ALL of the above ──build_db──▶ data/processed/restaurant_week.sqlite
                                                (DROPPED and rebuilt every run)
   build_venues: seeds `venues` (~1,420) + `venue_awards` (~1,941) from DB + award files
   resolve_venues: stamps Google identity/ratings from the committed cache (offline by default)

   export_venues ──▶ docs/data/venues.json        (roster page payload)
   export_site_data ──▶ docs/data/seasons/*.json  (dashboard payload, per season)
   export_places ──▶ docs/data/places.json        (must run after export_site_data)

   docs/index.html + venues.js   = roster site      (kejjeh.github.io/nyc-restaurants/)
   docs/restaurant-week.html + app.js = RW dashboard (…/restaurant-week.html)
```

`diff_report.py` runs last and prints what changed: the listing half compares the
two latest snapshots; the roster half compares `docs/data/venues.json` against
`git show HEAD:` (no sidecar history file). It also prints the human-owed queue —
pending entries in `recognition_review.json` / `venue_merge_review.json`.

## Key abstractions

- **Venue vs. participant.** `venues` is the universe; an award is a durable fact
  attached to a venue; RW participation is one season's attribute (`rw_slug`,
  nullable). Season payloads live under `docs/data/seasons/` keyed by
  `config/season.json`'s `code` (`srw26`).
- **Merge with asymmetric costs.** `build_venues.py` merges award records into
  venues. A false merge destroys data invisibly; a missed merge shows a visible
  duplicate. Rules therefore demand corroboration (shared address token, ZIP,
  etc.); pure string-similarity is banned as a decider. Undecidable pairs are
  written to `venue_merge_review.json` for a human, whose ruling is recorded
  permanently in `config/venue_aliases.json`.
- **Verified vs. estimate.** Prices/windows hand-checked from a restaurant's own
  printed materials are `verified`; heuristic website-sweep numbers are
  `estimate` and rendered as second-class everywhere. Never promote an estimate.
- **Guards over cleverness.** Fetchers refuse to overwrite good data with a
  suspicious crawl (e.g. a listing that would wipe most rows); exporters
  `--check` their own payload; CI re-derives `venues.json` and fails on drift.

## Boundaries a change is likely to cross

- Any DB schema/field change ⇒ both exporters ⇒ both payloads ⇒ both JS pages
  ⇒ tests in `tests/test_published_invariants.py` and roster/facet tests.
- Any award-file or merge-rule change ⇒ `build_venues` ⇒ review-queue contents
  ⇒ `diff_report` roster half.
- Season changeover touches ONLY `config/season.json` (plus new snapshots);
  everything else derives. If a changeover seems to need edits elsewhere, that's
  a bug — see README "Season changeover".
