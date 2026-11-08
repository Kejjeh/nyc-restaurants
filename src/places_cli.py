"""Track restaurants I want to try that are NOT in Restaurant Week.

Usage:
  python src/places_cli.py add "Le Bernardin" ["155 W 51st St"] [--dry-run]
  python src/places_cli.py list
  python src/places_cli.py remove <slug>

`add` resolves the name through the same Text Search machinery the roster uses
(src/fetch_google_ratings.py) and prints the top candidate for a y/n before
anything is written. `add` bills one Text Search; `add ... --dry-run` prints
the query it would send and its cost, without the key or the network. An
unknown argument is an error, raised before the key is read. There is no coordinate of our own to corroborate against
here, so the human confirmation IS the verification -- the same rule that lets
a hand-pinned place_id skip the geometry test.

Key: env GOOGLE_PLACES_KEY, else config/secrets.py (both gitignored). It is
never printed, never cached, and never enters a tracked file.

Writes config/places.json (tracked: the list itself) and, per place,
data/cache/places/<slug>.json in exactly the record shape data/raw/google/ uses,
so the exporter reads a place and a participant through one code path.
"""
import argparse
import json
import re
import shutil
import sqlite3
import tempfile
from pathlib import Path

from fetch_google_ratings import (TEXT_SEARCH_USD_PER_1000, TEXT_URL, api_key,
                                  best_candidate, get, norm)

ROOT = Path(__file__).resolve().parents[1]
PLACES = ROOT / "config" / "places.json"
CACHE = ROOT / "data" / "cache" / "places"
DB = ROOT / "data" / "processed" / "restaurant_week.sqlite"


def slugify(name):
    """Name -> the kebab shape a roster slug has. Apostrophes CLOSE UP
    ("Mark's" -> marks), which is what the program's own slugs do."""
    return "-".join(norm(re.sub(r"['’]", "", name or "")).split())


def load_places(path=PLACES):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    doc.setdefault("places", [])
    return doc


def save_places(doc, path=PLACES):
    Path(path).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")


def roster_slugs():
    """Slugs the program already owns, read live rather than from a copy."""
    if not DB.exists():
        return set()
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    try:
        return {r[0] for r in con.execute("SELECT slug FROM restaurants")}
    finally:
        con.close()


def reject_reason(slug, places, roster):
    """Why this slug cannot be added, or None. Every dashboard row is keyed by
    slug, so a collision does not merge two rows -- it hides one."""
    if not slug:
        return "empty slug"
    if any(p.get("slug") == slug for p in places):
        return f"{slug} is already on the list"
    if slug in roster:
        return f"{slug} is a Restaurant Week slug; pick another"
    return None


def add_place(doc, entry, roster):
    bad = reject_reason(entry.get("slug"), doc.get("places", []), roster)
    if bad:
        raise SystemExit(f"not added: {bad}")
    return {**doc, "places": [*doc.get("places", []), entry]}


def remove_place(doc, slug):
    kept = [p for p in doc.get("places", []) if p.get("slug") != slug]
    if len(kept) == len(doc.get("places", [])):
        raise SystemExit(f"{slug} is not on the list")
    return {**doc, "places": kept}


def query_for(name, hint):
    """The exact Text Search string resolve() sends; shared with --dry-run."""
    return " ".join(x for x in (name, hint, "New York") if x)


def resolve(name, hint, key):
    """Top Text Search candidate for a name -> the flattened match block.

    best_candidate is handed no coordinates on purpose: with nothing to
    corroborate, it falls back to ranking by name similarity, which is the most
    a machine can honestly do here.
    """
    q = query_for(name, hint)
    d = get(TEXT_URL, {"query": q, "key": key})
    if d.get("status") != "OK":
        raise SystemExit(f"search {d.get('status')}: "
                         f"{d.get('error_message', '')[:120]}")
    best = best_candidate(d["results"], name, None, None)
    if best is None:
        raise SystemExit(f"no usable result for {q!r}")
    return best[0]


def cache_record(slug, name, cand):
    """The confirmed match, in data/raw/google/'s record shape."""
    rec = {"slug": slug, "query_name": name, "matched": cand, "accepted": True,
           "reason": "confirmed by hand", "source": "confirmed", "error": None}
    CACHE.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / f"{slug}.json"
    tmp.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(tmp, CACHE / f"{slug}.json")
    return rec


def cmd_add(name, hint, dry_run=False):
    slug = slugify(name)
    doc = load_places()
    bad = reject_reason(slug, doc["places"], roster_slugs())
    if bad:
        raise SystemExit(f"not added: {bad}")
    if dry_run:
        print(f"1 Text Search would be sent for {slug}: {query_for(name, hint)}")
        print(f"estimated cost: ${TEXT_SEARCH_USD_PER_1000 / 1000:.3f} "
              f"at ${TEXT_SEARCH_USD_PER_1000:.0f}/1000 Text Search calls. "
              f"Dry run: no key read, nothing sent, nothing written.")
        return
    cand = resolve(name, hint, api_key())
    print(f"  {cand['name']}\n  {cand['address']}\n"
          f"  {cand['rating']}* ({cand['user_ratings_total']} reviews)"
          f" · {cand['business_status']}")
    if not input(f"add as {slug}? [y/N] ").strip().lower().startswith("y"):
        return print("not added")
    cache_record(slug, name, cand)
    save_places(add_place(doc, {"slug": slug, "name": name,
                                "address": cand["address"],
                                "place_id": cand["place_id"], "notes": None},
                          roster_slugs()))
    print(f"added {slug} -> config/places.json, cached data/cache/places/{slug}.json")


def cmd_list():
    places = load_places()["places"]
    print(f"{len(places)} place(s) on my list")
    for p in places:
        cached = "" if (CACHE / f"{p['slug']}.json").exists() else "  (no google match)"
        print(f"  {p['slug'][:34]:34} {(p.get('address') or '')[:40]}{cached}")


def cmd_remove(slug):
    save_places(remove_place(load_places(), slug))
    print(f"removed {slug} (data/cache/places/{slug}.json left alone)")


def parse_args(argv=None):
    """Strict: an unknown flag or a surplus argument exits 2 here, before a key
    is read. The old positional parsing took `add "X" --dry-run` as an address
    hint of "--dry-run" and sent a billed search with it."""
    ap = argparse.ArgumentParser(
        prog="places_cli.py",
        description="Track restaurants I want to try that are NOT in Restaurant Week.")
    sub = ap.add_subparsers(dest="cmd")
    add = sub.add_parser("add", help="resolve a name via Text Search (billed) and add it")
    add.add_argument("name")
    add.add_argument("hint", nargs="?", default=None, help="address hint")
    add.add_argument("--dry-run", action="store_true",
                     help="print the query and its cost; no key, no network")
    sub.add_parser("list", help="show the list (the default)")
    rm = sub.add_parser("remove", help="drop a slug from the list")
    rm.add_argument("slug")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.cmd in (None, "list"):
        return cmd_list()
    if args.cmd == "add":
        return cmd_add(args.name, args.hint, dry_run=args.dry_run)
    return cmd_remove(args.slug)


if __name__ == "__main__":
    main()
