"""Back-fill Michelin STAR history from Wikipedia's per-restaurant tables.

Usage: python src/backfill_michelin_stars.py [--from-file saved.html]

data/raw/recognition/michelin.json began as the 2025 selection only, which
made Michelin the one source on the roster with no history: a restaurant that
held a star in 2016 and lost it in 2020 showed no Michelin recognition at all
(issue 3). The guide's own site does not publish past selections, but
Wikipedia's "List of Michelin-starred restaurants in New York City" carries a
per-restaurant, per-year table for every NYC edition -- 2006-2010, 2011-2020
and 2021-2025 -- with the star count of each cell machine-readable in the
Parsoid `data-mw` attribute ({"stars": {"wt": "1"}}), not just an icon.

What this script deliberately does NOT do:

- Bib Gourmand and "recommended" stay 2025-only. No structured history for
  either exists anywhere found, and they are 81% of the 2025 file. The
  back-fill is stars only, and the README says so: this is a partial history,
  reliable exactly where the source is (stars), silent where it is not.
- The 2025 column is validated against the file, never written from
  Wikipedia. The guide's own selection is the better source for the year we
  have it; Wikipedia is the only source for the years we do not.
- Records land with no address -- Wikipedia gives neighbourhood, not street --
  so build_venues merges them on name alone or refuses into
  venue_merge_review.json, exactly like the Beard file's records.

Idempotent: every michelin record with year < 2025 is replaced by the parse,
so re-running against a newer copy of the page updates rather than duplicates.
"""
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MICHELIN = ROOT / "data" / "raw" / "recognition" / "michelin.json"
WIKI_URL = ("https://en.wikipedia.org/wiki/"
            "List_of_Michelin-starred_restaurants_in_New_York_City")
LEVEL = {1: "1 star", 2: "2 stars", 3: "3 stars"}


class Tables(HTMLParser):
    """Every <table> as rows of (text, attrs) cells, nested tables flattened
    out of the way. Only the three data tables (header row starting 'Name')
    are used."""

    def __init__(self):
        super().__init__()
        self.tables, self.stack = [], []
        self.row = self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.stack.append([])
        elif tag == "tr" and self.stack:
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell, self.cellattrs = "", dict(attrs)

    def handle_endtag(self, tag):
        if tag == "table" and self.stack:
            t = self.stack.pop()
            (self.stack[-1].append(t) if self.stack else self.tables.append(t))
        elif tag == "tr" and self.row is not None and self.stack:
            self.stack[-1].append(self.row)
            self.row = None
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append((self.cell.strip(), self.cellattrs))
            self.cell = None

    def handle_data(self, data):
        if self.cell is not None:
            self.cell += data


def stars_in(attrs, text):
    """A cell's star count: 0 for none/closed/not-yet-open, else 1-3.

    The count is read from the Parsoid data-mw JSON, which is the template
    argument itself -- not from counting <img> icons, which is presentation.
    """
    m = re.search(r'"stars":\s*\{\s*"wt":\s*"([a-z0-9]+)"', attrs.get("data-mw", ""))
    if m:
        return int(m.group(1)) if m.group(1).isdigit() else 0
    if not text or text.startswith(
            ("Closed", "Temporarily Closed", "Relocated", "\u2014", "-")):
        return 0
    raise ValueError(f"cell with no readable star count: {text[:40]!r}")


BOROUGHS = ("Manhattan", "Brooklyn", "Queens", "Bronx", "The Bronx",
            "Staten Island")


def parse(html):
    """-> {name: {year: stars}} across all three era tables.

    Rows whose Location is outside the five boroughs are dropped: the guide's
    NYC editions have covered Westchester (Blue Hill at Stone Barns, La
    Bastide by Andrea Calstier), and this roster is a New York City roster --
    the same ruling that keeps Matsuhisa LA out of the Beard records.
    """
    p = Tables()
    p.feed(html)
    out = {}
    for t in p.tables:
        if not t or not t[0] or t[0][0][0] != "Name":
            continue
        years = [int(c[0]) for c in t[0] if re.fullmatch(r"\d{4}", c[0])]
        lead = len(t[0]) - len(years)          # Name, Cuisine, Location
        for r in t[1:]:
            name = re.sub(r"\[\d+\]", "", r[0][0]).strip()
            if name == "Reference":     # the per-year citation row at the foot
                continue
            if not r[lead - 1][0].startswith(BOROUGHS):
                continue
            col = 0
            for text, attrs in r[lead:]:
                span = int(attrs.get("colspan", 1))
                n = stars_in(attrs, text)
                for i in range(span):
                    if col + i < len(years) and n:
                        out.setdefault(name, {})[years[col + i]] = n
                col += span
    return out


def main():
    if "--from-file" in sys.argv:
        html = Path(sys.argv[sys.argv.index("--from-file") + 1]).read_text(
            encoding="utf-8")
    else:
        req = urllib.request.Request(WIKI_URL, headers={
            "User-Agent": "nyc-restaurant-week-roster/1.0 "
                          "(github.com/Kejjeh/nyc-restaurants)"})
        html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")

    history = parse(html)
    records = json.loads(MICHELIN.read_text(encoding="utf-8"))
    y2025 = [r for r in records if r["year"] == 2025]

    # Wikipedia's row title vs the name the roster knows, where folding
    # cannot bridge them. Each entry is ruled by hand. The Torrisi one is not
    # cosmetic: Wikipedia's British spelling minted a fresh venue that
    # out-ranked the ledgered torrisi-italian-specialties row and retired its
    # slug -- the identity flip the ledger exists to prevent.
    NAME_FIX = {"63 Clinton": "Sixty Three Clinton",
                "Torrisi Italian Specialities": "Torrisi Italian Specialties"}

    def fold(n):
        import unicodedata
        n = unicodedata.normalize("NFKD", n)
        n = "".join(c for c in n if not unicodedata.combining(c)).casefold()
        n = re.sub(r"[^a-z0-9]+", "", n)
        return re.sub(r"newyork$", "", n)     # "Jungsik New York" is Jungsik

    # The year we already have from the guide itself is the validation set:
    # if Wikipedia disagrees with the file about 2025, the parse (or the page)
    # is wrong, and nothing should be written. Matching is by folded name --
    # the two sources spell "Noksu"/"Nōksu" and "L'Abeille"/"L’Abeille"
    # differently -- and the pairing doubles as a canonicaliser: a back-filled
    # record takes the guide file's spelling wherever one exists, so
    # build_venues merges history into the same venue the 2025 record made.
    file_stars = {fold(NAME_FIX.get(r["name"], r["name"])): r["name"]
                  for r in y2025 if r["level"].endswith(("star", "stars"))}
    wiki_2025 = {fold(NAME_FIX.get(n, n)): n
                 for n, ys in history.items() if ys.get(2025)}
    only_wiki = sorted(wiki_2025[k] for k in wiki_2025.keys() - file_stars.keys())
    only_file = sorted(file_stars[k] for k in file_stars.keys() - wiki_2025.keys())
    print(f"2025 cross-check: file {len(file_stars)} starred, "
          f"wikipedia {len(wiki_2025)}")
    if only_wiki:
        print("  only wikipedia:", ", ".join(only_wiki))
    if only_file:
        print("  only the file :", ", ".join(only_file))
    if len(only_wiki) + len(only_file) > 2:
        raise SystemExit("2025 disagreement is too large to be naming "
                         "variance -- refusing to write")

    canonical = {k: file_stars[k] for k in file_stars.keys() & wiki_2025.keys()}
    new = [{"name": canonical.get(fold(NAME_FIX.get(name, name)),
                                  NAME_FIX.get(name, name)),
            "address": None, "level": LEVEL[n], "year": year, "url": WIKI_URL}
           for name, ys in sorted(history.items())
           for year, n in sorted(ys.items()) if year < 2025]
    out = y2025 + new
    MICHELIN.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")
    years = sorted({r["year"] for r in new})
    print(f"wrote {len(out)} records: {len(y2025)} from the 2025 guide, "
          f"{len(new)} back-filled stars {years[0]}-{years[-1]} "
          f"across {len({r['name'] for r in new})} restaurants")


if __name__ == "__main__":
    main()
