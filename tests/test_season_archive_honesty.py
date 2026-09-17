"""The archive claimed to be complete on a snapshot that stopped 27 days early.

On 17 September 2026 — eleven days after Summer 2026 Restaurant Week closed —
the two published pages read:

    dashboard  "Summer 2026 has ended. The programme ran Jul 20 – Sep 6. This
                is the full-season archive: every participant is listed, none
                is still bookable."
    roster     "867 recognised restaurants, 636 of them in Summer 2026
                Restaurant Week (83 are both)."

Both were wrong, in opposite directions.

The dashboard asserted completeness it did not have. The last listing snapshot
the pipeline managed to publish was **10 August**, because the three refreshes
after it were refused — twice by the exporter's shrink guard (636 -> 459, then
636 -> 440) and once by the `min_rows: 400` floor in `fetch_listing` (308
unique records). Both guards were doing their job: the shrink was real, the
season was emptying. But the consequence is that `snapshot_date` (2026-08-10)
precedes `program_end` (2026-09-06), so the payload cannot be a full-season
archive, and the page's own footer printed the 10 August date directly beneath
the sentence claiming otherwise.

The roster said the opposite kind of untrue thing: present tense for a
programme that had finished. `program_end` was already in `venues.json` and the
page simply never read it.

Neither is fixable by re-running the exporter, and that is the point:

  * publishing the true tail needs BOTH guards overridden, which is an owner's
    decision, not an agent's; and
  * a re-export would not preserve this snapshot anyway. `scoring_day()` clamps
    the rubric's window component to `program_end`, so a post-season re-export
    is deterministic — but only against another post-season one. Re-exporting
    on 17 September moves the window component's mean from 21.7 to 2.1 and the
    rubric mean from 35.3 to 33.1, rewriting all 636 published grades. The
    mid-season snapshot is not reproducible, so it is preserved rather than
    regenerated.

So both fixes are copy: say what the data is, from fields the payload already
carries. These tests pin that the claim is conditional and that the condition
is the one that matters.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP_JS = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
VENUES_JS = (ROOT / "docs" / "venues.js").read_text(encoding="utf-8")


def archive_note():
    i = APP_JS.index("function archiveNote")
    return APP_JS[i:APP_JS.index("\n}\n", i)]


# ---------------------------------------------------------------- dashboard

def test_the_full_season_claim_is_conditional():
    """It may still be made — a season whose snapshot reaches its end IS a
    full-season archive. What it may not be is unconditional."""
    body = archive_note()
    assert "full-season archive" in body, "the true case must still be sayable"
    head = body[:body.index("full-season archive")]
    assert "snapshot_date" in head and "program_end" in head, (
        "the completeness claim must be guarded by comparing the snapshot "
        "against the end of the programme")


def test_the_guard_is_snapshot_before_end():
    """`snap < end` and nothing looser. `<=` would call a snapshot taken on the
    closing day incomplete, and it is not."""
    assert re.search(r"snap\s*<\s*end", archive_note())


def test_the_incomplete_branch_names_the_date_and_the_gap():
    """"Data may be incomplete" is a disclaimer. "Taken 10 August, 27 days
    before the season closed" is a fact the reader can act on."""
    body = archive_note()
    assert "fmtDate(snap)" in body, "the incomplete branch must print the as-of date"
    assert "daysBetween(snap, end)" in body, "and how far short of the end it stopped"


def test_the_incomplete_branch_makes_no_completeness_claim():
    """Sliced to the `snap < end` block, not to the end of the function. This
    read `body[body.index("const short"):]` while the completeness claim was
    the early return; once the branches were separated and it moved to the
    bottom, "everything after const short" swept it back in. The boundary the
    test means is the branch, so it says so."""
    body = archive_note()
    branch = body[body.index("const short"):]
    branch = branch[:branch.index("\n  }")]
    for forbidden in ("every participant is listed", "full-season"):
        assert forbidden not in branch, (
            f"the short-snapshot branch must not claim {forbidden!r}")


def test_days_between_is_whole_days_and_noon_anchored():
    """Anchored at 12:00Z like every other date helper here, so a DST shift
    cannot round the gap to the wrong day."""
    i = APP_JS.index("const daysBetween")
    body = APP_JS[i:i + 300]
    assert "T12:00:00Z" in body
    assert "Math.round" in body


# ------------------------------------------------------------------- roster

def test_the_roster_knows_the_season_can_end():
    assert "seasonEnded" in VENUES_JS
    i = VENUES_JS.index("const seasonEnded")
    body = VENUES_JS[i:i + 300]
    assert "program_end" in body, "the roster must read the field it already ships"
    assert "todayISO()" in body


def test_an_undated_season_stays_in_the_present_tense():
    """No end date is not an ending. The roster outlives its seasons and must
    not announce one it cannot date."""
    i = VENUES_JS.index("const seasonEnded")
    assert "!!end &&" in VENUES_JS[i:i + 300]


def test_the_roster_switches_tense_on_that_answer():
    i = VENUES_JS.index("function renderCoverage")
    body = VENUES_JS[i:VENUES_JS.index("\n}\n", i)]
    assert "seasonEnded()" in body
    assert "took part in" in body, "past tense once the programme has closed"
    assert "of them in" in body, "present tense while it is running"


def test_the_roster_says_when_it_ended():
    i = VENUES_JS.index("function renderCoverage")
    body = VENUES_JS[i:VENUES_JS.index("\n}\n", i)]
    assert "fmtDate(STATE.data.program_end)" in body


def test_the_roster_keeps_the_year_when_it_formats_a_date():
    """The dashboard's fmtDate drops the year because everything on it belongs
    to one season. The roster is year-round and carries seasons that have
    ended, so "Sep 6" alone would not say which September."""
    i = VENUES_JS.index("const fmtDate")
    assert "m[1]" in VENUES_JS[i:i + 300], "the roster's fmtDate must keep the year"


# ------------------------------------------------- the boundary, on both pages

def test_both_pages_treat_the_last_day_as_still_running():
    """`>` not `>=`, on both. The whole codebase treats the end date as
    inclusive — hasEnded, isUrgent, the planner and the countdown all do — and
    this page's own comment records the one place that did not and the 401
    restaurants it misread on the last day of the season."""
    i = VENUES_JS.index("const seasonEnded")
    assert re.search(r"todayISO\(\)\s*>\s*end", VENUES_JS[i:i + 300])
    j = APP_JS.index("function seasonPhase")
    assert re.search(r"t\s*>\s*DATA\.program_end", APP_JS[j:j + 500])


# ------------------------------------------------------- the published payload

def test_the_published_snapshot_really_does_stop_short():
    """The premise of this whole file. If a later refresh ever closes the gap,
    this fails and the conditional copy starts making the complete claim on its
    own — which is the intended behaviour, not a regression."""
    p = ROOT / "docs" / "data" / "seasons" / "srw26.json"
    if not p.exists():
        pytest.skip("payload not built")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["snapshot_date"] < d["program_end"], (
        "the summer 2026 payload is the 10 August snapshot of a season that "
        "ran to 6 September; if this is no longer true, re-read HANDOFF.md")


def test_the_registry_does_not_call_a_finished_season_live():
    """`update_registry` derives status from the build date, so the stamp is
    only as fresh as that season's last build. An ended season left marked
    `live` is the stale case the dashboard's seasonPhase() comment describes."""
    p = ROOT / "docs" / "data" / "seasons.json"
    if not p.exists():
        pytest.skip("registry not built")
    from datetime import date
    today = date.today().isoformat()
    for e in json.loads(p.read_text(encoding="utf-8"))["seasons"]:
        if today > e["end"]:
            assert e["status"] == "archived", (
                f"{e['code']} ended {e['end']} but the registry still says "
                f"{e['status']!r} — re-run export_site_data.py --registry-only")


# ------------------------------------- what the function actually returns
#
# Everything above reads the source text. That is enough to pin the shape of a
# branch, and it is not enough to pin which branch a payload lands on: the
# first cut of this guard read `!snap || !end || !(snap < end)`, which satisfies
# every source-text test in this file and still answered archiveNote({}) with
# "This is the full-season archive: every participant is listed". Three payload
# shapes -- no dates, end only, snapshot only -- took the completeness branch by
# falling through it, which is the repo's "null means unknown" rule inverted:
# absence resolved to the strongest sentence on the page rather than to an
# admission that the extent is unknown.
#
# So these call it. app.js is a browser script with no exports, so the harness
# loads the whole file with DOM globals stubbed and the trailing boot() removed,
# which is also a check worth having on its own: a top-level statement that
# cannot survive without a real DOM fails here.

NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const cut = src.replace(/\nboot\(\);\s*$/, '\n');
if (cut === src) { console.error('boot() call not found at the end of app.js'); process.exit(2); }
const stub = new Proxy(function () {}, {
  get: () => stub, set: () => true, apply: () => stub, construct: () => stub, has: () => true,
});
const load = new Function('document', 'window', 'location', 'fetch', 'localStorage',
  'requestAnimationFrame', 'navigator', cut + '\nreturn { archiveNote };');
const { archiveNote } = load(stub, stub, { search: '', hash: '' }, stub, stub, stub, stub);
const cases = JSON.parse(process.argv[3]);
const out = {};
for (const [name, payload] of Object.entries(cases)) out[name] = archiveNote(payload);
console.log(JSON.stringify(out));
"""

CASES = {
    "nothing":        {},
    "end_only":       {"program_end": "2026-09-06"},
    "snapshot_only":  {"snapshot_date": "2026-08-10"},
    "snapshot_null":  {"snapshot_date": None, "program_end": "2026-09-06"},
    "end_null":       {"snapshot_date": "2026-08-10", "program_end": None},
    "snapshot_junk":  {"snapshot_date": "not a date", "program_end": "2026-09-06"},
    "snapshot_absurd": {"snapshot_date": "2026-13-40", "program_end": "2026-09-06"},
    "short":          {"snapshot_date": "2026-08-10", "program_end": "2026-09-06"},
    "short_by_one":   {"snapshot_date": "2026-09-05", "program_end": "2026-09-06"},
    "on_the_day":     {"snapshot_date": "2026-09-06", "program_end": "2026-09-06"},
    "after_the_end":  {"snapshot_date": "2026-09-07", "program_end": "2026-09-06"},
}

UNDATABLE = ("nothing", "end_only", "snapshot_only", "snapshot_null", "end_null",
             "snapshot_junk", "snapshot_absurd")


@pytest.fixture(scope="module")
def notes():
    """One node run for the whole file: load app.js, call archiveNote on every
    shape, hand back what it said."""
    if not NODE:
        pytest.skip("node is not installed; the source-text tests above still run")
    harness = ROOT / "tests" / "_archive_note_harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    try:
        r = subprocess.run(
            [NODE, str(harness), str(ROOT / "docs" / "app.js"), json.dumps(CASES)],
            capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)
    assert r.returncode == 0, f"harness failed:\n{r.stderr}"
    return json.loads(r.stdout)


COMPLETE = "every participant is listed"


@pytest.mark.parametrize("case", UNDATABLE)
def test_an_undatable_payload_claims_no_completeness(notes, case):
    """The reported defect, one payload shape per id. Each of these returned
    the full-season sentence before the branches were separated."""
    said = notes[case]
    assert COMPLETE not in said, f"{case}: claimed completeness it cannot know"
    assert "full-season" not in said, f"{case}: called itself a full-season archive"


@pytest.mark.parametrize("case", UNDATABLE)
def test_an_undatable_payload_says_the_extent_is_unknown(notes, case):
    """Not claiming completeness is not the same as saying so. Silence reads as
    a complete archive to anyone who does not know the field exists."""
    said = notes[case]
    assert "unknown" in said, f"{case}: must name the uncertainty, not omit the claim"
    assert "partial record" in said, f"{case}: must say what to treat it as"


@pytest.mark.parametrize("case", UNDATABLE)
def test_an_undatable_payload_prints_no_date_and_no_gap(notes, case):
    """`fmtDate(undefined)` is null and `daysBetween` of a missing date is NaN.
    Neither may reach the page as "taken null" or "NaN days before"."""
    said = notes[case]
    assert "null" not in said and "NaN" not in said and "undefined" not in said, said


def test_a_short_snapshot_still_names_its_date_and_gap(notes):
    """The branch this file was written for is unchanged."""
    said = notes["short"]
    assert "Aug 10" in said and "27 days before the season closed" in said
    assert COMPLETE not in said


def test_the_gap_is_singular_at_one_day(notes):
    assert "1 day before" in notes["short_by_one"]
    assert "1 days" not in notes["short_by_one"]


def test_a_snapshot_that_reaches_the_end_is_still_a_full_season_archive(notes):
    """The true case must survive. `snap < end` is false on the closing day, and
    a season whose snapshot reaches its end really is complete."""
    assert COMPLETE in notes["on_the_day"]


def test_a_snapshot_taken_after_the_end_is_complete_too(notes):
    assert COMPLETE in notes["after_the_end"]


def test_the_published_payload_gets_the_short_snapshot_sentence(notes, request):
    """End to end on the real file, not a fixture: whatever docs/data carries
    today, the page's sentence must match it."""
    p = ROOT / "docs" / "data" / "seasons" / "srw26.json"
    if not p.exists():
        pytest.skip("payload not built")
    d = json.loads(p.read_text(encoding="utf-8"))
    if not NODE:
        pytest.skip("node is not installed")
    live = notes  # module fixture already ran; re-run for the real payload
    harness = ROOT / "tests" / "_archive_note_harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    try:
        r = subprocess.run(
            [NODE, str(harness), str(ROOT / "docs" / "app.js"),
             json.dumps({"live": {"snapshot_date": d.get("snapshot_date"),
                                  "program_end": d.get("program_end")}})],
            capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)
    assert r.returncode == 0, r.stderr
    said = json.loads(r.stdout)["live"]
    assert COMPLETE not in said, (
        "the published payload stops short of program_end, so the dashboard "
        "must not call it a full-season archive")
    assert "Aug 10" in said and live["short"] == said


# --------------------------------------- the sentence beside the claim
#
# Found by loading the page in a browser with `program_end` stripped from the
# payload in flight, which is the only way it shows: the unit harness above
# calls archiveNote directly and never reaches the clause before it.
#
#     "Summer 2026 has ended. The programme ran Jul 20 – null. ..."
#
# Both halves of that sentence assumed program_end was printable, and
# fmtDate(undefined) returns null, which a template literal stringifies. It is
# reachable on the published site rather than hypothetical: seasonPhase()
# returns 'archive' on the registry's `status` alone -- deliberately, because a
# stale stamp cannot wrongly un-end a season -- so the banner is drawn whether
# or not the payload carries the date it wants to print.

def season_over_banner():
    i = APP_JS.index("const over = $opt('#seasonOver')")
    return APP_JS[i:APP_JS.index("archiveNote(DATA)", i)]


def test_the_banner_does_not_print_a_date_it_does_not_have():
    """Guarded on isISODate, not on truthiness: `fmtDate` hands back its input
    unchanged for anything that is not an ISO date, so a truthy check would
    print "Jul 20 – not a date" instead of "Jul 20 – null"."""
    body = season_over_banner()
    assert "isISODate(DATA.program_end)" in body, (
        "the closing date must be checked before it is formatted")
    assert "isISODate(DATA.season_start)" in body


def test_the_banner_has_a_clause_for_a_start_without_an_end():
    """The case that produced "Jul 20 – null": a start date and no end. The
    start is real and still worth printing; the range is not."""
    body = season_over_banner()
    assert "The programme opened" in body


def test_no_branch_of_the_banner_interpolates_an_unguarded_end_date():
    """The defect was two template literals that both reached for
    program_end. Every remaining mention of it in this block is inside a
    branch that has already established it is a date."""
    body = season_over_banner()
    ran = body.index("const ran = isISODate")
    assert "fmtDate(DATA.program_end)" not in body[:ran], (
        "program_end is formatted before it is checked")
