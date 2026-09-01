# Decision log

Settled choices, reconstructed from code comments, commit history, and the README.
Do not re-litigate these; if one truly must change, say why the original reason no longer holds.
"(inferred)" marks rationale deduced rather than found stated.

## Data & methodology

- **Roster-as-spine.** The award roster is the primary dataset; Restaurant Week participation is
  a nullable column on it, not the other way round. Chosen when the repo pivoted from a season
  tracker to `nyc-restaurants` (commit 2e95a35); the old tracker was frozen as its own repo.
- **Slug identity via a ledger, not name matching.** `data/venue_slugs.json` records every slug
  ever issued; reuse requires address-evidence fit, contradiction mints a fresh slug, nothing is
  deleted. Rejected alternative: recomputing slugs each build — it silently changed identities
  when inputs shifted (commits 14f8b72, e0ede92).
- **Bayesian shrinkage with `GOOGLE_PRIOR = 150`**, defined once in `config.py`. Chosen against
  the actual review-count distribution (reasoning in README). The roster page once drifted to its
  own prior of 300 and ordered 452 rows differently — hence the single definition, with the
  frontend reading the prior from the payload.
- **Verified > listing > sweep.** A restaurant's own printed materials
  (`config/verified_values.json`) beat the listing API; `price_sweep` output is heuristic triage
  and may never populate a "verified" field. One gap definition (`price_sweep.gaps_for`);
  a published gap must reconcile with the two published numbers (commits fe156e1, dc092bf).
- **Null means unknown.** Never 0, never false, never rendered as a zero-width bar or a 0 score.
  Two rubric components once scored 0 where the zero was not a fact (commit dc092bf).
- **Ambiguity goes to a human.** Uncertain venue merges and recognition matches land in
  `data/processed/*_review.json` for a ruling recorded in config; the pipeline never guesses.
- **Geographic sanity is ZIP-based, not bbox-based.** `NYC_BOUNDS` exists only to reject
  far-away geocodes (Oakland, San Angelo); borough membership uses ZIP prefixes because the
  bbox contains NJ, Yonkers, and Nassau (accepted Bayonne/Passaic venues before the ZIP gate).
- **Michelin history back-filled from Wikipedia** (`backfill_michelin_stars.py`), cross-checked
  against the 2025 guide snapshot with a refuse-to-write threshold — the live guide silently
  forgets delisted restaurants, so the snapshot alone under-reported (commits e7d06ec, 9529dfe).

## Publishing & ToS

- **Menu PDFs are never committed or hosted** (NYC Tourism ToS). Enforced by both workflows;
  PDFs live only in the Actions cache and local disk.
- **Published menu text is budgeted**: ≤5% of a menu's text or 40 chars, with a tighter internal
  cap so an outside audit always finds margin (commit b5be3ae pulled a keyword that blew the budget).
- **≤1 request/sec to nyctourism**, single-flight refresh (`concurrency: rw-refresh`), and the
  site's public x-api-key is re-discovered from its JS bundles on 403 rather than hardcoded forever.
- **Payload shrink guard (80%)**: exporters refuse to publish a payload that lost >20% of rows
  without `--allow-shrink`, because an upstream failure once looked like a quiet shrink.
- **Write-if-changed** with `generated_at` ignored, so weekly commits only happen when data moved.

## Site

- **Vanilla JS, no framework, no build step.** (inferred: a personal tool served raw from
  `docs/` on GitHub Pages; a toolchain would add cost with no payoff at this size.)
- **Two CSP tiers.** Roster page allows no third-party origin at all — which forced the
  hand-rolled SVG borough map (commit f1007d4, "without the CSP toll it feared"). Dashboard
  allows exactly unpkg (Leaflet) + CARTO tiles, lazy-loaded on first map open so the list view
  makes zero third-party requests.
- **Precomputed payloads, dumb client.** All scoring/ranking happens in Python; the browser
  filters and sorts only. (inferred: keeps the two pages consistent and the logic testable.)
- **Facet counts are computed excluding the facet's own selections** so a second value in a
  group stays reachable; `tools/verify_ui_counts.mjs` exists because this regressed repeatedly.
- **Hash-URL state on the dashboard only**, fully validated on read (unknown facets dropped,
  dates round-tripped, sort looked up with `Object.hasOwn`). Roster filters are deliberately
  not shareable. (inferred: dashboard links get shared; roster is browsed.)
- **`?v=N` cache-busting by hand** instead of hashed filenames — no build step to do it.

## Testing & automation

- **Python tests assert on frontend source text** (regex over `app.js`/`venues.js`/CSS) instead
  of adding a JS test harness. Rejected alternative: a Node test stack — heavier than the site
  itself. Browser-level verification is the separate, manual `verify_ui_counts.mjs`.
- **Each test file's docstring names the bug it prevents** — the suite doubles as the incident log.
- **CI never crawls and holds no secrets.** `checks.yml` is offline: tests + PDF guard +
  `--check` validators + a staleness guard that rebuilds the roster payload and diffs it.
  The weekly `refresh.yml` crawls and commits data back as `github-actions[bot]`.
- **`GOOGLE_PLACES_KEY` is deliberately not in CI** — undecided whether to add an Actions secret
  or keep ratings fetches local (README flags it; see HANDOFF.md open questions).
- **Prep-branch note (2026-09-01):** `.gitignore` was narrowed from ignoring all of `.claude/`
  to ignoring only local state, so the repo can share `launch.json`, agent settings, and slash
  commands. Decided during handoff prep to make agent workflows reproducible.
