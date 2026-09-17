"""Every URL on the roster comes from outside the roster.

Two of them reach an `href`:

  * an award record's `source_url`, from the crawled award files;
  * `rw.reserve`, which is `reservation_link or website or listing_url` — and
    `website` comes straight from the Restaurant Week listing API, re-pulled
    every week and written into the payload without a human reading it.

`app.js` checks the scheme before assigning an href, in eight places, with
`isHttpURL`. `venues.js` did it in none, on the same data.

Serving a poisoned payload with `javascript:` in those two fields, before the
fix:

    bookHrefs   ["javascript:window.__PWNED_BOOK=1"]
    jsHrefs     2

Two live `javascript:` links in the DOM, one of them the Book button. (A
synthetic click in a headless browser does not navigate a `javascript:` href,
so what is demonstrated is that the value reaches the attribute — the part this
code controls — not the execution, which is the browser's part.)

After: the Book link is not rendered at all, the award falls back to the plain
text it already has for records with no URL, and `jsHrefs` is 0.

Today's payload is clean — 2,576 https, one http, nothing else — so this was a
latent hole rather than a live one. It is guarded because the weekly refresh
reaches the payload unreviewed, and because the guard already existed one file
over.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VENUES_JS = (ROOT / "docs" / "venues.js").read_text(encoding="utf-8")
APP_JS = (ROOT / "docs" / "app.js").read_text(encoding="utf-8")


def test_the_roster_has_a_scheme_guard_at_all():
    assert "isHttpURL" in VENUES_JS


def test_it_accepts_only_http_and_https():
    i = VENUES_JS.index("const isHttpURL")
    body = VENUES_JS[i:i + 400]
    assert "https?:" in body
    assert "new URL(" in body, "parse it rather than string-matching a prefix"
    assert "catch" in body, "an unparseable URL must be refused, not thrown on"


def test_every_href_in_the_roster_is_guarded():
    """The rule, not the two instances: nothing may assign an href without
    having checked it first."""
    for m in re.finditer(r"^\s*(\w+)\.href = (.+);$", VENUES_JS, re.M):
        target, value = m.group(1), m.group(2).strip()
        if value.startswith("`") and "encodeURIComponent" in value:
            continue                      # an internal, encoded fragment link
        before = VENUES_JS[max(0, m.start() - 300):m.start()]
        assert "isHttpURL(" in before, (
            f"{target}.href = {value} is assigned without a scheme check")


def test_both_pages_use_the_same_rule():
    """They render the same fields from the same pipeline."""
    for src in (APP_JS, VENUES_JS):
        i = src.index("const isHttpURL")
        assert "https?:" in src[i:i + 400]


def _url_call(src):
    """The `new URL(...)` argument list inside isHttpURL."""
    i = src.index("const isHttpURL")
    m = re.search(r"new URL\(([^)]*)\)", src[i:i + 600])
    assert m, "isHttpURL must parse the value with new URL()"
    return m.group(1)


# ids= is not cosmetic: the source text IS the param, and pytest writes each
# test id into an environment variable Windows caps at 32,767 characters. Both
# files cross it, which is what produced the phantom Windows errors PR #45
# chased out of test_payload_fetch.py. Same shape here, same remedy.
@pytest.mark.parametrize("src", [VENUES_JS, APP_JS], ids=["venues.js", "app.js"])
def test_no_base_is_passed_to_url(src):
    """A bare hostname must be refused, and only a base-less URL() refuses it.

    `venues.js` passed `location.href` as the base. `new URL("www.joesbar.com",
    location.href)` does not throw — it RESOLVES, relative to the page, and
    comes back with an `http:` protocol, so the scheme test passed and the Book
    button got an href pointing at `docs/www.joesbar.com`: a 404 on our own
    origin, under a link whose text promises the restaurant.

    `rw.reserve` is `reservation_link or website or listing_url`, and `website`
    arrives from the listing API unreviewed, so a scheme-less value there is an
    ordinary thing to receive rather than a poisoned one. This was never the
    XSS hole — `javascript:` and `data:` were refused throughout — it was a
    link that lied about where it went.

    Pinned as "exactly one argument" because that IS the behaviour: with a base
    every relative string resolves, and there is no base that makes a bare
    hostname fail.
    """
    assert "," not in _url_call(src), (
        "isHttpURL must call new URL(u) with no base — a base makes "
        "'www.joesbar.com' resolve against the page and pass the check")


def test_the_two_pages_now_agree_character_for_character():
    """The dashboard's implementation was correct all along and documented why.
    Divergence between two copies of one rule is how this survived; equality is
    the cheapest way to keep them honest."""
    def body(src):
        i = src.index("const isHttpURL")
        return re.sub(r"\s+", " ", src[i:src.index("};", i) + 2])
    assert body(VENUES_JS) == body(APP_JS)


def test_the_award_keeps_its_text_when_the_url_is_refused():
    """A refused link must not take the award record with it — the row already
    knows how to render one with no URL."""
    i = VENUES_JS.index("isHttpURL(a.url)")
    block = VENUES_JS[i:i + 700]
    assert "} else {" in block
    assert "awardWhat" in block.split("} else {")[1]


@pytest.mark.parametrize("field", ["url", "reserve"])
def test_the_published_payload_carries_only_http_urls(field):
    p = ROOT / "docs" / "data" / "venues.json"
    if not p.exists():
        pytest.skip("payload not built")
    d = json.loads(p.read_text(encoding="utf-8"))
    bad = []
    for v in d["venues"]:
        urls = ([a.get("url") for a in v["recognition"]] if field == "url"
                else [(v.get("rw") or {}).get("reserve")])
        for u in urls:
            if u and not re.match(r"^https?://", u):
                bad.append(f"{v['slug']}: {u[:60]}")
    assert not bad, "\n  ".join([""] + bad[:10])
