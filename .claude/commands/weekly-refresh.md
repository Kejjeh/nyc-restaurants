# Run the weekly refresh locally

CI does this every Monday (refresh.yml); run locally only when asked.

1. `python -m pytest -q tests/` — abort if not green.
2. `python src/refresh.py` (network, ~10+ min, rate-limited ≤1 req/sec — never parallelize).
   Add `--force-menus` ONLY if asked to catch in-place menu edits (~10 min extra).
3. Read the diff report it prints. Surface to the user: SHORTLIST ALERTS, closures,
   season-boundary lines, and the pending-rulings counts at the end.
4. `python -m pytest -q tests/` again; then `python src/export_site_data.py --check --quiet`
   and `python src/export_venues.py --check --quiet`.
5. `git ls-files | grep -i '\.pdf$'` must print nothing.
6. Show `git status` to the user. Commit only if asked; never push unasked.

KNOWN STATE (since Aug 10): step 2 currently FAILS on purpose — `fetch_listing` hits
`min_rows: 400` (the live listing is ~308 as the season ends) and, past that, the exporters
refuse the >20% shrink. Both guards are correct. Do not lower `min_rows` or pass
`--allow-shrink` to get a green run; that decision belongs to the owner (HANDOFF.md P0).

If the listing crawl refuses to run or reports a wiped/replaced roster: STOP and
tell the user — that guard exists on purpose (possible season changeover; see
README "Season changeover", and escalate per CLAUDE.md model routing).
