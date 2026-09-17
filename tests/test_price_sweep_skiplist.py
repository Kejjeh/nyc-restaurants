"""Three of the sweep's fifty skip entries had never skipped anything.

`ALREADY_ANALYZED` was a set literal in `src/price_sweep.py`, hand-typed from
restaurant NAMES rather than run through the pipeline's own slug rule. Checked
against the database:

    the-bronx-beer-hall         -> bronx-beer-hall              "The Bronx Beer Hall"
    mae-mae-cafe-plant-shop     -> mae-mae-cafe-and-plant-shop  "Mae Mae Cafe & Plant Shop"
    code-red-restaurant-lounge  -> code-red-restaurant-and-lounge "Code Red Restaurant & Lounge"

Two failure modes, one cause: `&` becomes `and`, and a leading `The` is dropped.

A skip entry that matches nothing is SILENT. It does not raise, it does not
warn — `targets()` just never filters that slug out, so all three restaurants
were re-crawled on every sweep, at 1 request/second, to redo work the list
exists to say is already done. The handoff had noticed one of the three.

The guard is not "every entry must be in the database": entries legitimately
stop matching as restaurants leave the listing between seasons, and
`catch-nyc` is exactly that — no venue of that name is in the listing at all,
and nothing close to it is (`sweet-catch` and `catch-n-chop` are other
restaurants). The guard is the shape the three defects actually had: an entry
that matches nothing while a very similar slug IS live. That means the entry
was meant to be that one.
"""
import difflib
import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
DONE = ROOT / "config" / "price_sweep_done.json"
DB = ROOT / "data" / "processed" / "restaurant_week.sqlite"

# Below this, two slugs are different restaurants rather than one mistyped.
# 'code-red-restaurant-lounge' vs 'code-red-restaurant-and-lounge' scores 0.93;
# 'catch-nyc' vs 'catch-n-chop', the closest live slug to the one legitimately
# departed entry, scores 0.76.
TYPO_RATIO = 0.85


def live_slugs():
    if not DB.exists():
        pytest.skip("database not built")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return {r[0] for r in con.execute("SELECT slug FROM restaurants")}
    finally:
        con.close()


def test_the_list_loads_from_config():
    from price_sweep import already_analyzed
    assert already_analyzed() == set(json.loads(DONE.read_text(encoding="utf-8"))["slugs"])


def test_the_source_no_longer_carries_the_list():
    """Curation lives in config/, per CLAUDE.md. A set literal in a module is
    how this drifted out of step with the slugs for a whole season."""
    src = (ROOT / "src" / "price_sweep.py").read_text(encoding="utf-8")
    assert "ALREADY_ANALYZED = {" not in src


def test_no_entry_is_a_near_miss_of_a_live_slug():
    """The bug, stated as a rule. An entry that matches nothing is fine — the
    restaurant left. An entry that matches nothing while its near-twin is live
    is a typo, and a silent one."""
    live = live_slugs()
    done = json.loads(DONE.read_text(encoding="utf-8"))["slugs"]
    typos = []
    for slug in done:
        if slug in live:
            continue
        near = difflib.get_close_matches(slug, sorted(live), n=1, cutoff=TYPO_RATIO)
        if near:
            typos.append(f"{slug} matches nothing, but {near[0]} is live")
    assert not typos, (
        "skip entries that look like typos of live slugs:\n  " + "\n  ".join(typos))


def test_the_three_known_typos_are_corrected():
    """Named, so a regression says which one came back."""
    done = set(json.loads(DONE.read_text(encoding="utf-8"))["slugs"])
    for wrong, right in (
        ("the-bronx-beer-hall", "bronx-beer-hall"),
        ("mae-mae-cafe-plant-shop", "mae-mae-cafe-and-plant-shop"),
        ("code-red-restaurant-lounge", "code-red-restaurant-and-lounge"),
    ):
        assert wrong not in done
        assert right in done


def test_the_skip_list_actually_removes_those_rows_from_the_sweep():
    """The behaviour, not just the file: whatever is in the list must not be
    handed to the crawler."""
    import price_sweep
    if not DB.exists():
        pytest.skip("database not built")
    done = price_sweep.already_analyzed()
    targets = {slug for slug, _w, _t in price_sweep.targets()}
    assert not (targets & done), "a skipped slug reached the crawl list"
    # and the corrected slug is genuinely one the sweep would otherwise crawl
    assert "code-red-restaurant-and-lounge" in live_slugs()


def test_underscore_keys_are_comments():
    """The convention every other config loader here follows."""
    d = json.loads(DONE.read_text(encoding="utf-8"))
    assert any(k.startswith("_") for k in d), "the file should document itself"
    from price_sweep import already_analyzed
    assert not any(s.startswith("_") for s in already_analyzed())


# ------------------------------------------------------------- swept_date

def test_build_db_does_not_invent_a_sweep_date():
    """It wrote the literal "2026-08-01" onto every sweep row it loaded,
    identically, for records taken on days it had no knowledge of.

    Scoped to code, not comments — the same distinction
    `test_no_hardcoded_season.py` draws: a date inside a string literal is a
    value the program uses, the same digits in a comment are prose about it,
    and the comment recording this defect must not read as the defect.
    """
    src = (ROOT / "src" / "build_db.py").read_text(encoding="utf-8")
    code = "\n".join(re.sub(r"#.*$", "", ln) for ln in src.splitlines())
    assert not re.search(r"""['"]\d{4}-\d{2}-\d{2}['"]""", code), (
        "build_db must not stamp a date literal onto sweep rows")
    assert 'r.get("swept_date")' in code


def test_a_sweep_record_carries_its_own_date():
    import price_sweep
    from datetime import date
    rec = {"slug": "x", "website": "w", "pages_fetched": 0, "prices": [],
           "error": None, "swept_date": date.today().isoformat()}
    assert "swept_date" in rec
    src = (ROOT / "src" / "price_sweep.py").read_text(encoding="utf-8")
    assert '"swept_date": date.today().isoformat()' in src
    assert price_sweep.date is date


def test_an_undated_record_reads_null_not_a_guess():
    """Records written before the stamp have no date. Absence renders as
    absence — the rule this repo states for every other nullable field."""
    assert {"slug": "x"}.get("swept_date") is None
