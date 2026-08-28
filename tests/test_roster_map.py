"""The roster's map view, and the property that shaped it.

Issue 2 closed with 631 of 1,340 venues mappable and named the map as the
work it unblocked -- with one warning: the roster page's CSP allows no
third-party origin at all, and that is "a real property worth keeping". The
dashboard pays the Leaflet/CARTO toll on its own page; the roster does not.
So the map is local SVG over a committed borough shoreline, and these tests
hold the property as much as the feature.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "docs" / "index.html").read_text(encoding="utf-8")
JS = (ROOT / "docs" / "venues.js").read_text(encoding="utf-8")
CSS = (ROOT / "docs" / "venues.css").read_text(encoding="utf-8")
BOROUGHS = ROOT / "docs" / "data" / "boroughs.json"


def csp_of(html):
    m = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]*)"',
                  html, re.S)
    assert m, "the roster page must carry a CSP"
    return m.group(1)


def test_the_map_did_not_cost_the_page_its_csp():
    """The reason this map is not Leaflet. Every directive stays 'self' (plus
    data: for the favicon); if a third-party origin ever appears here, the
    map stopped being worth it."""
    csp = csp_of(HTML)
    origins = re.findall(r"https?://\S+", csp)
    assert origins == [], f"the roster page now allows {origins}"
    assert "unpkg" not in csp and "cartocdn" not in csp


def test_the_outlines_are_committed_small_and_in_the_city():
    """The basemap is data, so it is committed like data. Small enough that
    the map costs less wire than the payload it decorates, and every point
    inside the bounds the roster already refuses to publish beyond."""
    import config
    assert BOROUGHS.exists(), "run src/fetch_borough_outlines.py"
    assert BOROUGHS.stat().st_size < 100_000
    geo = json.loads(BOROUGHS.read_text(encoding="utf-8"))
    names = {b["name"] for b in geo["boroughs"]}
    assert names == {"Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"}
    for b in geo["boroughs"]:
        assert b["rings"], f"{b['name']} has no outline at all"
        for ring in b["rings"]:
            assert len(ring) >= 4
            for lng, lat in ring:
                assert config.in_nyc(lat, lng), (
                    f"{b['name']} outline point ({lat}, {lng}) is outside "
                    "the bounds the roster itself enforces")


def test_the_outline_fetch_has_the_same_deadline_as_the_payloads():
    """The same hole test_payload_fetch closes: a request that is accepted
    and never answered must not hang the map forever."""
    assert "timedFetch" in JS
    body = JS[JS.index("async function timedFetch"):JS.index("function buildMap")]
    assert "AbortController" in body
    assert "FETCH_TIMEOUT_MS" in body
    assert "clearTimeout(timer)" in body and "finally" in body
    assert "timedFetch(BOROUGHS_URL)" in JS


def test_a_venue_without_coordinates_is_counted_not_invented():
    """The map must skip unresolved venues AND say how many it skipped --
    silently plotting fewer rows than the list shows reads as 'covered
    everything' when it did not."""
    body = JS[JS.index("function renderMap"):JS.index("function setView")]
    assert "v.lat == null" in body
    assert "have no confirmed location" in body


def test_the_map_fails_toward_the_list():
    """If the outlines cannot load, the page must say so and leave the list
    -- which carries every venue the map would have shown -- fully working."""
    body = JS[JS.index("function setView"):JS.index("function wireMapDetail")]
    assert "The list view has everything" in body
    assert "AbortError" in body and "did not answer within" in body


def test_the_dots_are_the_lists_rows():
    """A dot click renders the venue through renderRow -- the one renderer
    both views share -- not through a second, drifting card template."""
    body = JS[JS.index("function wireMapDetail"):JS.index("function renderCoverage")]
    assert "renderRow(v)" in body


def test_the_toggle_and_containers_exist_and_the_map_starts_hidden():
    assert 'id="viewList"' in HTML and 'id="viewMap"' in HTML
    assert 'aria-pressed' in HTML
    assert re.search(r'<section id="mapView" hidden', HTML)


def test_the_stylesheet_was_cache_busted_for_the_map():
    """A cached venues.css against a fresh venues.js would render the map
    unstyled; the ?v= bump is what prevents that."""
    m = re.search(r'venues\.css\?v=(\d+)', HTML)
    assert m and int(m.group(1)) >= 11
    assert ".mapWrap" in CSS and ".mapDots" in CSS


def test_the_dot_statuses_are_the_pill_statuses():
    """One vocabulary: the same three states the status pills use, so the
    map cannot show a fourth truth the list does not have."""
    for status in ("open", "closed", "unknown"):
        assert f".mapDots .dot.{status}" in CSS
