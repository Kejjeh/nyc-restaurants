"""The roster blamed filters for a typo, in a sentence it never wrote.

`index.html` ships a static `<p id="emptyMsg">Nothing matches those
filters.</p>` and `venues.js` never touched it. So every empty result on the
roster said the same thing, beside a Clear filters button — including a search
for a misspelled restaurant, which is the commonest way to reach zero rows and
the one case where clearing filters cannot help.

The dashboard had this bug and it was fixed one wave earlier; the roster is the
same shape of page reading the same kind of payload, and I did not check it at
the time.

It is worse here. The roster's filters start empty — no default date filter, no
default anything — so on a fresh page a search that misses produces "Nothing
matches those filters" when *no filter exists at all*.

What decides the wording is whether the term matches anything IGNORING the
filters. "Are filters set" answers a different question.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "docs" / "venues.js").read_text(encoding="utf-8")
HTML = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")


def body_of(name):
    start = JS.index(f"function {name}(")
    depth, i = 0, JS.index("{", start)
    for j in range(i, len(JS)):
        if JS[j] == "{":
            depth += 1
        elif JS[j] == "}":
            depth -= 1
            if depth == 0:
                return JS[start:j + 1]
    raise AssertionError(f"unbalanced braces in {name}")


def test_the_page_writes_its_own_empty_message():
    assert "function emptyMessage(" in JS
    assert "#emptyMsg" in JS, "the static HTML was the only thing that ever said it"


def test_it_is_called_whenever_there_is_nothing_to_show():
    fn = body_of("apply")
    assert "emptyMessage()" in fn
    assert "!hits.length" in fn


def test_the_branch_turns_on_whether_the_search_matched_anything():
    fn = body_of("emptyMessage")
    assert "haystack(v).includes(STATE.q)" in fn, (
        "the wording must depend on the search, not on whether filters are set")


def test_a_term_that_matches_nothing_is_sent_to_the_spelling():
    fn = body_of("emptyMessage")
    assert "Check the spelling" in fn
    assert "$('#q')" in fn, "the term itself should be named back to the reader"


def test_a_term_the_filters_removed_says_so_and_counts_them():
    fn = body_of("emptyMessage")
    assert "the filters remove them all" in fn
    assert "loose === 1" in fn, "one restaurant should not be 'restaurants'"


def test_the_three_jury_preset_gets_its_own_sentence():
    """It is not a facet, so "those filters" would not point at anything the
    reader can see to undo."""
    fn = body_of("emptyMessage")
    assert "STATE.threeWay" in fn
    assert "all three juries" in fn


def test_an_empty_roster_is_not_blamed_on_the_reader():
    fn = body_of("emptyMessage")
    assert "!STATE.rows.length" in fn
    assert "not with anything you set" in fn


def test_the_static_fallback_is_still_a_sentence():
    """A reader with JavaScript half-loaded should not see an empty box."""
    m = re.search(r'id="emptyMsg"[^>]*>([^<]+)<', HTML)
    assert m and m.group(1).strip(), "the HTML fallback went missing"


def test_both_pages_answer_the_same_question():
    app = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")
    for src, name in ((app, "app.js"), (JS, "venues.js")):
        assert "Check the spelling" in src, f"{name} does not name a bad term"
        assert "the filters remove them all" in src, f"{name} does not name the filters"


# --------------------------------------------------------------------- $opt

def test_roster_chrome_lookups_degrade_instead_of_dying():
    """A cached index.html against a fresh venues.js rendered a blank page.

    index.html and venues.js are cached independently, so a returning visitor
    can hold yesterday's HTML against today's JS. Boot is one call chain, so
    the first `$('#thing').textContent = ...` against an element only the newer
    HTML has threw and took the whole roster with it. The `?v=` on the script
    tag prevents the opposite pairing and cannot help with this one.

    Reproduced in Chromium by serving an index.html with `#coverage` and
    `#footProvenance` stripped out:

        with $   ->  0 rows, "Cannot set properties of null (setting 'textContent')"
        with $opt -> 120 rows, no page errors

    The dashboard has had this guard since it had chrome to miss. #rows stays
    on `$` deliberately: with no row host there is no page to degrade into, and
    a thrown error beats a silent blank.
    """
    src = (ROOT / "docs" / "venues.js").read_text(encoding="utf-8")
    assert "const $opt = (sel) => document.querySelector(sel) || el('span');" in src
    for sel in ("#coverage", "#rosterCount", "#footProvenance"):
        assert f"$opt('{sel}')" in src, f"{sel} is chrome and must use $opt"
        assert f"$('{sel}')" not in src, f"{sel} still has a bare $ lookup"
    assert "$('#rows')" in src, "#rows is essential and must stay on $"
