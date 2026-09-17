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
    tail = archive_note()
    tail = tail[tail.index("const short"):]
    for forbidden in ("every participant is listed", "full-season"):
        assert forbidden not in tail, (
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
