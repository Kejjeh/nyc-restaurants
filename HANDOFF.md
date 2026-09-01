# HANDOFF — state of play (written 2026-08-29)

Read CLAUDE.md first. This file is what's true *right now*.

## Done and working
- Full pipeline + weekly Monday refresh (refresh.yml) + PR checks (checks.yml). Green.
- Live site: https://kejjeh.github.io/nyc-restaurants/ (roster) and
  `/restaurant-week.html` (Summer 2026 value dashboard). Both verified loading clean.
- Roster: ~1,420 venues, ~1,941 award records; Michelin stars back-filled 2006–2024.
- 474 tests pass (2 previously failed on Windows only — fixed on this branch, see below).
- Sister repo: the pre-roster season tracker lives at Kejjeh/nyc-restaurant-week
  (frozen, refresh disabled). Don't confuse the two.

## In progress / recently touched
- **Issue #3 (Michelin history), remaining open items** — deliberately parked:
  - Bib Gourmand / "recommended" pre-2025 history: no source exists; stays 2025-only.
  - Undecided design questions: should the recency factor apply per-source, and
    should `top_honor` be best-ever? Both need a human decision, not code.
- **Human review queues are non-empty** (the pipeline is waiting on rulings):
  - `data/processed/recognition_review.json`: 5 michelin + 8 james_beard + 1 nyt records.
  - `data/processed/venue_merge_review.json`: 1 in `confirm`, 4 `refused`,
    10 `group_award_parts_unmatched`, 77 `awards_to_a_person_with_no_room`.
  - Process: an agent may research and *present* each case; only the human rules.
    Rulings go in `config/venue_aliases.json` (merges) or the award files.

## Known bugs
- ~~`tests/test_diff_report_boundary.py` (2 tests) failed on Windows~~ — fixed on
  this branch: `diff_report.previous_payload()` ran `git show` through
  `subprocess.run(text=True)` without `encoding="utf-8"`; cp1252 decode died in
  the reader thread, stdout came back `None`, `json.loads(None)` → TypeError.
  Repro (pre-fix): run the suite on Windows. Linux CI never saw it.
- No other known failing tests. The Windows `PermissionError ... pytest-current`
  after a green run is noise (temp-dir cleanup), not a failure.

## Prioritized next steps
- **P0 — Season end 2026-09-06 (next week).** After end, confirm the dashboard
  flips to archive mode by itself (it should; `seasonPhase()` in app.js).
  Acceptance: site opens on archive view, no console errors, weekly diff report
  prints "season ended" behavior rather than mass-DROPPED noise.
- **P0 — Merge this branch** (`prep/handoff-20260829`) after human review.
  Acceptance: checks.yml green; suite green on Windows too.
- **P1 — Present the review queues to the human** (one session: read both files,
  research each pending record, write a short recommendation per record; make
  NO ruling). Acceptance: a markdown summary the human can approve line-by-line.
- **P1 — Winter 2027 changeover, when announced.** Follow README "Season
  changeover (winter 2027)" exactly: edit `config/season.json` only, run refresh,
  check the transition guards. Escalate to Opus. Acceptance: guards pass, new
  `docs/data/seasons/<code>.json` exists, old season archived.
- **P2 — Wire `tools/verify_ui_counts.mjs` into CI** (needs a browser in the
  runner; playwright install step). Acceptance: checks.yml runs it headless and green.
- **P2 — Decide the two parked issue-#3 questions** (per-source recency;
  best-ever top_honor). Human decision first; implementation is small after that.

## Open questions (for the human)
- This prep chose the ROSTER repo (folder "NYC Restaurant Week" → Kejjeh/nyc-restaurants)
  as "the repository" being handed off, since the tracker repo is frozen. Confirm.
- ARCHITECTURE.md / DECISIONS.md sit at repo ROOT, not `docs/` as the prep spec
  asked: `docs/` here is the published Pages site and Jekyll would publish them.
- The two issue-#3 design questions above.
- Local folder names still don't match repo names (roster lives in folder
  "NYC Restaurant Week"); rename was blocked by a process lock — do it from an
  external terminal when convenient.

## Tech debt (known, not urgent)
- README.md is 1,455 lines and drifts (it said "289 tests"; corrected to point
  at reality on this branch). Treat CLAUDE.md as the agent entry point.
- `verify_ui_counts.mjs` is manual-only (see P2).
- `data/raw/` is ~427MB locally; a fresh clone re-downloads 473 menu PDFs on
  first refresh (~10 min at 1 req/sec) — expected, not a bug.
- `docs/app.js` and `docs/venues.js` are large single files by design (no build
  step). Don't split them without a decision.
