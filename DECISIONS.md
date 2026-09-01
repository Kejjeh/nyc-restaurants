# Decision log

Settled decisions with their reasons. Do not re-litigate; if one truly must be
reopened, say so explicitly to the human first. Sources: commit messages, README,
issue threads. Items marked "(inferred)" were reconstructed, not found stated.

## Scope & data model
- **The roster is the spine; Restaurant Week is an attribute** (`0e9af3b`). The
  original universe was "this summer's 636 participants". Rejected because awards
  outlive seasons; ~796 never-in-RW venues are first-class rows. The pre-roster
  season tracker was frozen as its own repo (`2e95a35`).
- **Snapshot files are dated and immutable; the DB is disposable.** `build_db`
  drops and rebuilds; raw snapshots are the record. Rejected alternative:
  incremental DB updates (harder to trust after partial failures). (inferred)
- **Diff baseline is `git show HEAD:venues.json`, not a sidecar history file**
  — HEAD is already versioned and immutable; the sidecar approach (used by the
  older menu-hash section) makes the report write state, so re-runs lie.
- **Null means unknown — never 0, never false** (`dc092bf`). Applies from the DB
  through the payloads to rendering (no zero-width bars for missing data).
- **Geographic sanity is ZIP-based, not bbox-based.** `NYC_BOUNDS` only rejects
  far-away geocodes (Oakland/San Angelo); borough membership uses ZIP prefixes,
  because the bbox also contains NJ, Yonkers and Nassau (it once admitted
  Bayonne and Passaic venues).

## Venue merging
- **Thresholds favor missed merges over wrong merges** — a wrong merge silently
  turns two restaurants into one; a miss is a visible duplicate.
- **String-ratio similarity may suggest, never decide.** The ratio orders
  Upper East/Upper West (must stay apart, 0.969) ABOVE Sant/Saint Ambroeus
  (must fold, 0.963). Spelling variants need a corroborating token.
- **An address we lack is not a contradiction**; a shared ZIP can rescue a
  second entrance; portfolio awards ("Outstanding Restaurateur" naming three
  restaurants) are split, not treated as a venue.
- **Humans break ties, permanently.** Undecidable pairs go to
  `venue_merge_review.json`; rulings live in `config/venue_aliases.json` and are
  never re-asked. Slugs are ledgered (`data/venue_slugs.json`) so a folded slug
  can't be re-minted as a fresh venue (`e0ede92`).

## Awards & recognition
- **Michelin history is stars-only 2006–2024** from Wikipedia's per-edition
  tables (1,195 records), validated against the 2025 file (issue #3, PR #43).
  Bib Gourmand / "recommended" have no usable historical source; they stay
  2025-only and an absent pre-2025 Bib means *missing data, not a fact*.
- **The 2025 Michelin file snapshots the LIVE guide, which silently drops
  delisted restaurants** (Shion 69 Leonard St restored by hand, `9529dfe`).
- **Awards age; they don't expire.** Recency discounts an award's weight rather
  than a threshold deleting it; a 1993 award is shown with its year, not as news
  (`aefd57a`, `77ac77e`).
- **Awards to a person with no restaurant attached don't create venues**
  ("Anthony Bourdain was a restaurant", `e7edff4`); they're parked in the review
  file (`awards_to_a_person_with_no_room`).

## Scoring (the rubric)
- **Crowd outweighs critics; the award is aged, not scored** (`77ac77e`).
- **Google ratings are Bayes-shrunk toward the mean** so a 4.9 from 14 reviews
  cannot lead (`fee22b4`); `export_places` shrinks toward the *roster* mean.
  **The prior (150) is defined once, in `config.py`** — the roster page once
  drifted to its own prior of 300 and ordered 452 rows differently.
- **The "value" component was dropped from the rubric** (`bf25dde`); missing
  components are imputed at their own mean; weights target "the dinner, not the
  deal" (`55fddbb`). Rating is a floor/filter, not blended into best-value (`9386c0f`).
- **Zero is only printed where zero is a fact** (`dc092bf`).

## ToS & publishing
- **Public repo is authorized by a direct conversation with NYC Tourism: text
  extraction fine, hosting their exact menu PDFs prohibited.** Hence: PDFs
  gitignored, CI guard, menus linked to the official S3 URL only. If ever
  contradicted, go private again (README top).
- **Published menu text is budgeted**: ≤5% of a menu's text or 40 chars, with a
  tighter internal cap so an outside audit always finds margin (`b5be3ae`).
- **Crawl politely: ≤1 req/sec**, enforced per-process in `src/config.py`;
  refresh workflows never overlap (concurrency group).
- **Exporters refuse to publish a payload that shrank >20%** without
  `--allow-shrink` — an upstream failure once looked like a quiet shrink.

## Site
- **No framework, no build step, vanilla JS + hand-built SVG charts.** Rejected:
  chart libs and bundlers — the payload is small and the site must stay
  auditable/cheap. (inferred from code; stated for charts in app.js comments)
- **Two CSP tiers.** The roster page allows no third-party origin at all — which
  forced its hand-rolled SVG borough map (`f1007d4`). The dashboard accepts
  exactly unpkg (Leaflet) + CARTO tiles, lazy-loaded on first map open.
- **Third-party URLs are validated (`isHttpURL`) before hitting an href**
  (`4365434`); external links carry `rel="noopener noreferrer"`.
- **Facet counts are promises** — every number printed on a control must equal
  the rows clicking it yields; `tools/verify_ui_counts.mjs` exists to re-check.

## Testing & operational
- **Python tests assert on frontend source text** (regex over `app.js` /
  `venues.js` / CSS) instead of adding a JS test harness — heavier than the site
  itself. Browser-level verification is the separate, manual `verify_ui_counts.mjs`.
- **Each test file's docstring names the bug it prevents** — the suite doubles
  as the incident log. Read it before "fixing" a test.
- **Tests run before the crawl, and also on every PR** (`c362d89`, checks.yml)
  so a broken guard fails in seconds, not after ten minutes of polite fetching.
- **CI re-derives `venues.json` and fails on drift** — the site must never be a
  build behind its own committed data. `generated_at` is excluded from the
  comparison (it's the wall clock; including it would make the check cry wolf).
- **CI holds no secrets and never crawls.** `GOOGLE_PLACES_KEY` is deliberately
  not an Actions secret (undecided — see HANDOFF.md open questions); the weekly
  refresh skips ratings and the cache carries them.
- **Handoff prep (2026-09-01):** `.gitignore` narrowed from ignoring all of
  `.claude/` to tracking `.claude/commands/` (agent runbooks); `.claudeignore`
  added to keep the 427 MB of data and generated payloads out of agent context.
  ARCHITECTURE.md / DECISIONS.md sit at repo root because `docs/` is published.
