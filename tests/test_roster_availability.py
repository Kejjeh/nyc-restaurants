"""The roster's rows advertised an archived offer as a live one.

Walked on 19 September 2026 — thirteen days after Summer 2026 Restaurant Week
closed — against the published payload, in a real browser, at 1280x900 and at
390x844. The page as a whole knew the season was over: the coverage banner read
"That programme ended Sep 6, 2026; its prices and menus are over."

The rows did not. Every one of the 636 Restaurant Week rows rendered

    Dhamaka  [Open]  [Restaurant Week $60]                      ... [Book]

in the dashboard's "value" green — the loudest colour either page owns for
"this is worth money" — with the tooltip "Open this restaurant on the value
dashboard — its prix fixe, menu, gap against à la carte and subway walk", all
of it in the present tense. Re-driven against a payload whose `program_end` was
in the future, and against one with no `program_end` at all, the row rendered
IDENTICALLY in all three. The row is what carries a price, a banner at the top
of a 1,420-row page is not standing next to it, and a price with no tense on it
is read as a price.

Three further things fell out of the same walk, each reproduced before it was
touched:

  * `seasonEnded()` was a boolean, so "we cannot date this season" had to land
    on one of its two answers, and it landed on `false` — the present tense,
    which is the claim that these prices are ones you can still get. Missing,
    null and "2026-13-40" all did it. The junk date is the sharpest: the check
    was a STRING comparison, "2026-09-19" > "2026-13-40" is false, so an
    unparseable date read as a season still running. This is the dashboard's
    archiveNote defect — unknown falling through to the strongest claim — in
    the same repo, on the same kind of missing date, three days later.

  * A payload without `season_label` printed the literal string
    "undefined Restaurant Week".

  * The roster held its state in memory and nowhere else. Filter to the
    Michelin-starred rooms, search "brooklyn", get 21 of 1,420, open one on the
    value dashboard — which is what the Restaurant Week pill is for, and which
    navigates in the same tab — then press Back: 120 of 1,420, no chips, empty
    search box. The one gesture every browser promises will undo a navigation
    threw the work away.

  * The detail card under the map outlived the selection it was part of. Tap a
    dot on a phone, then search for something that matches nothing: zero dots,
    "Nothing matches", and the tapped restaurant still sitting there with its
    Book link, inside a region the markup labels "Map of the current selection".

What these tests pin is that the row answers the season question at all, that
the answer has three values and not two, and that the page can be returned to.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "docs" / "venues.js").read_text(encoding="utf-8")
CSS = (ROOT / "docs" / "venues.css").read_text(encoding="utf-8")
HTML = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
NODE = shutil.which("node")


def body_of(name, end=None):
    """One function or const block, sliced at its own closing brace."""
    i = JS.index(name)
    return JS[i:JS.index(end, i)] if end else JS[i:JS.index("\n}\n", i)]


# --------------------------------------------------------- what the row says

def test_the_row_asks_what_the_season_is_doing():
    """The whole defect in one assertion: before this, nothing inside renderRow
    mentioned the season, so the pill read the same in July and in September."""
    block = body_of("function renderRow")
    assert "seasonState()" in block, (
        "the Restaurant Week pill must be rendered against the season's state, "
        "not unconditionally")


def test_the_pill_says_ended_and_keeps_the_price():
    """Keeping the money matters: what the prix fixe WAS is a true fact and it
    is why the row is worth reading. What it must not do is read as an offer."""
    block = body_of("function renderRow")
    assert "' · ended'" in block
    assert "price_tiers" in block, "the price stays on the pill"


def test_the_pill_marks_an_undatable_season_too():
    """Not ended, not running: the third answer needs its own words on the
    control, or unknown quietly borrows whichever neighbour is more flattering."""
    block = body_of("function renderRow")
    assert "dates unconfirmed" in block


def test_the_book_link_stops_implying_the_restaurant_week_price():
    """The link itself is fine year-round -- it is the restaurant's own
    reservations page -- so the word "Book" stays and the accessible name says
    which prices are on the other side of it."""
    block = body_of("function renderRow")
    i = block.index("class=\"reserve\"") if "class=\"reserve\"" in block else block.index("'reserve'")
    tail = block[i:]
    assert "normal prices" in tail
    assert "seasonState()" in tail


def test_the_ended_pill_loses_the_value_green():
    """A colour is a claim as much as a word is. The live pill borrows the
    dashboard's value green; over a closed season that is an advertisement."""
    assert ".pill.rw.ended" in CSS
    assert ".pill.rw.unknown" in CSS
    ended = CSS[CSS.index(".pill.rw.ended"):CSS.index(".pill.rw.unknown")]
    assert "--value" not in ended, "the ended pill must not keep the value colour"
    unknown = CSS[CSS.index(".pill.rw.unknown"):]
    assert "dashed" in unknown.split("}")[0], (
        "unknown takes the dashed border this page already uses for 'we do not know'")


def test_the_stylesheet_and_script_were_cache_busted():
    """index.html and venues.js/css are cached independently; a stale pair is
    how this page once rendered nothing at all."""
    assert "venues.js?v=16" in HTML
    assert "venues.css?v=12" in HTML


# ------------------------------------------------ what the coverage line says

def test_the_unknown_branch_makes_no_claim_about_availability():
    block = body_of("function renderCoverage")
    i = block.index("state === 'unknown'")
    branch = block[i:]
    assert "unknown" in branch
    assert "rather than as something you can book" in branch
    assert "of them in" not in branch, (
        "the present tense is the claim that these prices are still buyable")


def test_a_season_with_no_label_is_not_called_undefined():
    """`${label} Restaurant Week` against a payload without one rendered the
    literal string "undefined Restaurant Week"."""
    block = body_of("const seasonLabel", end="};")
    assert "trim()" in block and "null" in block
    cov = body_of("function renderCoverage")
    assert "seasonLabel()" in cov
    assert "'Restaurant Week'" in cov, "the fallback names the programme without a season"


# --------------------------------------------- the state itself, in real node

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const cut = src.replace(/\nboot\(\);\s*$/, '\n');
if (cut === src) { console.error('boot() call not found at the end of venues.js'); process.exit(2); }
const stub = new Proxy(function () {}, {
  get: () => stub, set: () => true, apply: () => stub, construct: () => stub, has: () => true,
});
/* ?today= is the debug hook venues.js already carries, and it is read at load
   time -- which is what lets this harness ask what the page would say on a
   given day without waiting for that day. */
const today = process.argv[4];
const load = new Function('document', 'window', 'location', 'fetch', 'localStorage',
  'requestAnimationFrame', 'navigator', 'history', 'matchMedia',
  cut + '\nreturn { STATE, seasonState, seasonLabel, isISODate };');
const api = load(stub, stub, { search: `?today=${today}`, hash: '', pathname: '/' },
                 stub, stub, stub, stub, stub, stub);
const cases = JSON.parse(process.argv[3]);
const out = {};
for (const [name, payload] of Object.entries(cases)) {
  api.STATE.data = payload;
  out[name] = { state: api.seasonState(), label: api.seasonLabel() };
}
console.log(JSON.stringify(out));
"""

TODAY = "2026-09-19"
CASES = {
    "ended":          {"program_end": "2026-09-06", "season_label": "Summer 2026"},
    "ends_today":     {"program_end": "2026-09-19", "season_label": "Summer 2026"},
    "ends_tomorrow":  {"program_end": "2026-09-20", "season_label": "Summer 2026"},
    "missing":        {"season_label": "Summer 2026"},
    "null":           {"program_end": None, "season_label": "Summer 2026"},
    "empty":          {"program_end": "", "season_label": "Summer 2026"},
    "junk":           {"program_end": "2026-13-40", "season_label": "Summer 2026"},
    "rolled":         {"program_end": "2026-02-30", "season_label": "Summer 2026"},
    "not_a_string":   {"program_end": 20260906, "season_label": "Summer 2026"},
    "no_label":       {"program_end": "2026-09-06"},
    "blank_label":    {"program_end": "2026-09-06", "season_label": "   "},
}
UNDATABLE = ("missing", "null", "empty", "junk", "rolled", "not_a_string")


@pytest.fixture(scope="module")
def states():
    """One node run for the file: load venues.js with the DOM stubbed out and
    ask seasonState() what it makes of each payload."""
    if not NODE:
        pytest.skip("node is not installed; the source-text tests above still run")
    harness = ROOT / "tests" / "_roster_state_harness.js"
    harness.write_text(HARNESS, encoding="utf-8")
    try:
        r = subprocess.run(
            [NODE, str(harness), str(ROOT / "docs" / "venues.js"),
             json.dumps(CASES), TODAY],
            capture_output=True, text=True, timeout=60)
    finally:
        harness.unlink(missing_ok=True)
    assert r.returncode == 0, f"harness failed:\n{r.stderr}"
    return json.loads(r.stdout)


@pytest.mark.parametrize("case", UNDATABLE)
def test_an_undatable_season_is_neither_running_nor_ended(states, case):
    """The correction this file exists for. A boolean had to put unknown on one
    of two answers and put it on the flattering one."""
    assert states[case]["state"] == "unknown", (
        f"{case} -> {states[case]['state']}: a date the page cannot read must "
        "not decide whether an offer is live")


def test_a_junk_date_does_not_read_as_a_running_season(states):
    """"2026-09-19" > "2026-13-40" is false as a string comparison, so the
    original check called an unparseable date a season still going."""
    assert states["junk"]["state"] == "unknown"


def test_a_date_that_does_not_exist_is_not_a_date(states):
    """Date.parse rolls 2026-02-30 to March 2 without complaint; only the
    round-trip catches it."""
    assert states["rolled"]["state"] == "unknown"


def test_a_closed_season_reads_as_ended(states):
    assert states["ended"]["state"] == "ended"


def test_the_last_day_is_still_running(states):
    """`>` not `>=`. The end date is inclusive everywhere in this codebase --
    hasEnded, isUrgent, the planner, the countdown -- and on the last day of
    the season you can still eat the menu."""
    assert states["ends_today"]["state"] == "running"
    assert states["ends_tomorrow"]["state"] == "running"


def test_a_missing_label_comes_back_as_nothing_not_as_text(states):
    assert states["no_label"]["label"] is None
    assert states["blank_label"]["label"] is None
    assert states["ended"]["label"] == "Summer 2026"


# ------------------------------------------------------- the URL is the state

def test_every_control_records_itself():
    """apply() is the one funnel every control goes through; writing the URL
    anywhere else would mean "most controls"."""
    block = body_of("function apply")
    assert "writeHash()" in block


def test_the_page_reads_its_url_before_it_draws():
    block = body_of("async function boot")
    assert "readHash()" in block
    assert block.index("readHash()") < block.index("if (STATE.view === 'map')"), (
        "state must be restored before the first render, or the page draws twice")


def test_the_url_carries_the_filters_the_search_and_the_sort():
    block = body_of("function writeHash")
    for token in ("STATE.filters", "'juries'", "'q'", "'sort'", "'view'", "'n'"):
        assert token in block, f"{token} is part of where you were"


def test_the_url_does_not_fill_the_back_button():
    """One history entry per keystroke would make Back useless in the other
    direction -- which is the same bug, mirrored."""
    assert "history.replaceState" in body_of("function writeHash")
    assert "pushState" not in JS


def test_an_unknown_facet_value_in_the_url_is_ignored():
    """An accepted-but-impossible value adds a chip that can match nothing, and
    the page then reads "0 of 1,420" -- blaming a filter for a value that does
    not exist. The dashboard's readHash carries this scar already."""
    block = body_of("function readHash")
    assert "knownFacetValues" in block


def test_a_sort_key_from_the_url_is_checked_with_hasown():
    """`sort=constructor` is inherited from Object.prototype: it passes a
    truthy check and is then called as a comparator."""
    block = body_of("function readHash")
    assert "Object.hasOwn(SORTS" in block


def test_a_row_count_from_the_url_has_to_be_a_count():
    block = body_of("function readHash")
    assert "Number.isInteger" in block


def test_editing_the_url_of_an_open_page_does_something():
    """Changing only the hash is a same-document navigation, so boot() does not
    re-run: a URL pasted into the bar of an already-open roster silently did
    nothing, and the page went on showing one selection while its own URL
    described another. Found by pasting one, three minutes after the URL state
    it depends on was written. app.js has carried this since it had filters and
    its comment says the same thing."""
    # "function wire" alone matches wireMapDetail first -- it is defined
    # earlier in the file.
    block = body_of("function wire()")
    assert "'hashchange'" in block
    i = block.index("'hashchange'")
    handler = block[i:]
    assert "clearFilters()" in handler, (
        "the pasted URL replaces the selection rather than adding to it")
    assert "readHash()" in handler


# --------------------------------------------------- the card under the map

def test_the_map_detail_card_cannot_outlive_the_selection():
    """It sits inside a region the markup labels "Map of the current
    selection", so a venue the current filters exclude stops being shown in
    it."""
    block = body_of("function renderMap")
    assert "STATE.pinned" in block
    assert "hits.some" in block
    wired = body_of("function wireMapDetail", end="function renderCoverage")
    assert "STATE.pinned = slug" in wired


def test_the_map_region_still_claims_to_be_the_current_selection():
    """If this label ever stops saying "current selection", the test above is
    pinning a promise the page no longer makes."""
    assert re.search(r'aria-label="Map of the current selection"', HTML)
