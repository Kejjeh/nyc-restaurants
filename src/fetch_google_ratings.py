"""Fetch Google Places ratings for each restaurant.

Usage: python src/fetch_google_ratings.py [--shard i/k] [--force] [--report] [--dry-run]
  --dry-run  print what would be fetched and what it would cost, without
             reading the key or sending anything
  An unknown argument is an error, raised before the key is read or anything
  is sent: a mistyped --dry-run once ran a real, billed fetch.

Key: env GOOGLE_PLACES_KEY, else config/secrets.py (both gitignored). It is
never written into the cache, the payload, or any tracked file.

Billing: one Text Search per uncached restaurant. Results are cached per slug
so re-runs cost nothing; only --force re-bills.

MATCHING IS THE HARD PART, not fetching. Text Search returns a best guess for
a name, and a name is not an identifier -- searching "53" returns a restaurant
621m away. Every result is therefore checked against the coordinates and name
we already hold, and anything that fails is recorded as UNMATCHED with its
reason rather than being accepted. config/google_place_ids.json overrides the
search with a hand-verified place_id, which is the only truly stable key.

Output: data/raw/google/{slug}.json
"""
import argparse
import importlib.util
import json
import os
import re
import shutil
import tempfile
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from math import radians, sin, cos, asin, sqrt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "google"
DB = ROOT / "data" / "processed" / "restaurant_week.sqlite"
OVERRIDES = ROOT / "config" / "google_place_ids.json"

TEXT_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
DETAIL_FIELDS = ("name,formatted_address,geometry/location,place_id,rating,"
                 "user_ratings_total,business_status")

# Accept outright when the point is this close -- two geocoders for the same
# address rarely differ by more than a building width.
NEAR_M = 150
# Beyond this, no name similarity rescues it: it is a different restaurant.
FAR_M = 400
NAME_MIN = 0.55
PAUSE = 0.12

# Places Text Search, US list price at the time of writing, per 1,000 calls.
# Only ever used to print an estimate before spending anything; nothing in the
# pipeline depends on it being current. (resolve_venues.py imports it from here.)
TEXT_SEARCH_USD_PER_1000 = 32.0


SECRETS_FILE = ROOT / "config" / "secrets.py"
NO_KEY = ("No API key. Set GOOGLE_PLACES_KEY, or copy config/secrets.example.py "
          "to config/secrets.py and fill it in.")


def load_secrets_module():
    """config/secrets.py as a module, loaded by path. None when there is no file.

    It used to be `sys.path.insert(0, ROOT/"config")` followed by
    `from secrets import GOOGLE_PLACES_KEY`, which had two problems.

    The insert put `config/` FIRST on `sys.path`, for the rest of the process,
    so every module name in there outranks the standard library. `secrets` IS a
    standard library module — the one `token_urlsafe`, `compare_digest` and
    friends live in — so after one call to `api_key()` any later `import
    secrets`, ours or a dependency's, got the key file instead. Nothing in this
    repo imports it today; that is luck, not design, and the failure would be
    silent and remote from here.

    So: load the file by its path under a private name, register nothing
    importable as `secrets`, and leave `sys.path` alone.
    """
    if not SECRETS_FILE.exists():
        return None
    spec = importlib.util.spec_from_file_location(
        "_nycr_secrets", SECRETS_FILE)          # not "secrets": see above
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)                # may raise; the caller decides
    return mod


def api_key():
    """The Places key, from the environment or config/secrets.py.

    The old version wrapped the whole load in `except Exception` and reported
    every outcome as "No API key" — including a `SyntaxError` in secrets.py, a
    file that raises on import, and a file that simply spells the name wrong.
    All three read as "you have not set one up", so the advice was to do the
    thing already done, and a typo could be chased for a long time. A key that
    is present and broken is a different fact from a key that is absent.

    Never printed, never logged, never included in a message: this returns it
    and says nothing about its value.
    """
    k = os.environ.get("GOOGLE_PLACES_KEY")
    if k:
        return k
    try:
        mod = load_secrets_module()
    except Exception as e:
        raise SystemExit(
            f"config/secrets.py exists but could not be loaded: "
            f"{type(e).__name__}: {e}\n"
            f"Fix the file, or unset it and use GOOGLE_PLACES_KEY instead.")
    if mod is None:
        raise SystemExit(NO_KEY)
    key = getattr(mod, "GOOGLE_PLACES_KEY", None)
    if not key:
        raise SystemExit(
            "config/secrets.py loaded, but GOOGLE_PLACES_KEY is missing or empty. "
            "config/secrets.example.py shows the expected shape.")
    return key


def norm(s):
    """Fold a name for comparison. Also shapes place slugs via places_cli.slugify."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s)).strip()


def name_sim(a, b):
    """Token-set similarity in [0,1]. Either side being a subset scores 1.0 --
    which is why callers need an exact-name tiebreak on top."""
    A, B = set(norm(a).split()), set(norm(b).split())
    if not A or not B:
        return 0.0
    if A <= B or B <= A:
        return 1.0
    return len(A & B) / len(A | B)


def haversine_m(a_lat, a_lng, b_lat, b_lng):
    d1, d2 = radians(b_lat - a_lat), radians(b_lng - a_lng)
    h = (sin(d1 / 2) ** 2
         + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(d2 / 2) ** 2)
    return 2 * 6371000 * asin(sqrt(h))


def get(url, params, tries=3):
    """GET with backoff on OVER_QUERY_LIMIT; returns {"status": "UNKNOWN_ERROR"}
    on exhaustion rather than raising -- every caller branches on "status"."""
    u = f"{url}?{urllib.parse.urlencode(params)}"
    for i in range(tries):
        try:
            with urllib.request.urlopen(u, timeout=30) as r:
                d = json.loads(r.read())
            if d.get("status") == "OVER_QUERY_LIMIT" and i < tries - 1:
                time.sleep(2 + 2 * i)
                continue
            return d
        except urllib.error.URLError:
            if i == tries - 1:
                raise
            time.sleep(1 + i)
    return {"status": "UNKNOWN_ERROR"}


def judge(cand, name, lat, lng):
    """-> (accepted, reason). Distance is the primary evidence; the name only
    rescues a mid-range hit, and nothing rescues a far one."""
    if lat is None or lng is None:
        return False, "no coordinates on our side to corroborate"
    d = haversine_m(lat, lng, cand["lat"], cand["lng"])
    s = name_sim(name, cand["name"])
    if d <= NEAR_M:
        return True, f"{round(d)}m away"
    if d <= FAR_M and s >= NAME_MIN:
        return True, f"{round(d)}m away, name agrees ({s:.2f})"
    return False, f"{round(d)}m away, name similarity {s:.2f}"


def flatten(res):
    """Canonical "matched" record shape. A cross-module contract: resolve_venues,
    places_cli, export_places and export_site_data all read these exact keys."""
    loc = (res.get("geometry") or {}).get("location") or {}
    return {
        "place_id": res.get("place_id"),
        "name": res.get("name"),
        "address": res.get("formatted_address"),
        "rating": res.get("rating"),
        "user_ratings_total": res.get("user_ratings_total"),
        "business_status": res.get("business_status"),
        "lat": loc.get("lat"), "lng": loc.get("lng"),
    }


MAX_CANDIDATES = 5


def best_candidate(results, name, lat, lng):
    """Best of the top few Text Search hits -> (candidate, accepted, reason),
    or None when none of them carried coordinates.

    results[0] alone is not enough: the best name match is not always first when
    a chain's other branches rank higher. A rejected best is still RETURNED with
    its reason -- recording why we refused is the whole point of this file.
    """
    best = None
    for res in results[:MAX_CANDIDATES]:
        c = flatten(res)
        if c["lat"] is None:
            continue
        ok, why = judge(c, name, lat, lng)
        # An exact name outranks a subset: both score 1.00 ("Masa" is a subset
        # of "Bar Masa"), and when a chain's other branch ranks first in the
        # results, the tie used to go to whichever Google listed first.
        score = (ok, norm(name) == norm(c["name"]), name_sim(name, c["name"]))
        if best is None or score > best[0]:
            best = (score, (c, ok, why))
    return best[1] if best else None


def query_for(name, hood, boro):
    """The exact Text Search string fetch_one() sends. Shared with --dry-run so
    the preview shows what the billed run would send, not a reimplementation."""
    return " ".join(x for x in (name, hood, boro, "New York") if x)


def fetch_one(slug, name, hood, boro, lat, lng, key, place_id=None):
    rec = {"slug": slug, "query_name": name, "matched": None,
           "accepted": False, "reason": None, "source": None, "error": None}
    try:
        if place_id:
            d = get(DETAILS_URL, {"place_id": place_id, "key": key,
                                  "fields": DETAIL_FIELDS})
            if d.get("status") != "OK":
                rec["error"] = f"details {d.get('status')}"
                return rec
            # A hand-pinned place_id IS the verification; no geometry test.
            rec.update(matched=flatten(d["result"]), accepted=True,
                       reason="hand-verified place_id", source="place_id")
            return rec
        q = query_for(name, hood, boro)
        d = get(TEXT_URL, {"query": q, "key": key})
        rec["source"] = "textsearch"
        if d.get("status") == "ZERO_RESULTS":
            rec["reason"] = "no result for the query"
            return rec
        if d.get("status") != "OK":
            rec["error"] = f"{d.get('status')}: {d.get('error_message', '')[:120]}"
            return rec
        best = best_candidate(d["results"], name, lat, lng)
        if best is None:
            rec["reason"] = "no result carried coordinates"
            return rec
        c, ok, why = best
        rec.update(matched=c, accepted=ok, reason=why)
    except Exception as e:
        rec["error"] = f"{type(e).__name__}: {str(e)[:120]}"
    return rec


def targets():
    import sqlite3
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return con.execute(
        "SELECT slug, name, neighborhood, borough, lat, lng FROM restaurants"
        " ORDER BY slug").fetchall()


def write(rec):
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp()) / f"{rec['slug']}.json"
    tmp.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.copyfile(tmp, OUT / f"{rec['slug']}.json")


def report():
    files = sorted(OUT.glob("*.json"))
    acc = [json.loads(f.read_text(encoding="utf-8")) for f in files]
    ok = [a for a in acc if a["accepted"]]
    rej = [a for a in acc if not a["accepted"] and not a["error"]]
    err = [a for a in acc if a["error"]]
    print(f"cached {len(acc)} · accepted {len(ok)} · rejected {len(rej)} · errored {len(err)}")
    rated = [a for a in ok if a["matched"].get("rating") is not None]
    if rated:
        rs = sorted(a["matched"]["rating"] for a in rated)
        tot = sorted(a["matched"]["user_ratings_total"] or 0 for a in rated)
        print(f"with a rating: {len(rated)} · median {rs[len(rs)//2]}★ "
              f"· median reviews {tot[len(tot)//2]}")
    if rej:
        print("\nrejected (kept as unmatched, never guessed):")
        for a in rej[:25]:
            m = a["matched"] or {}
            print(f"  {a['slug'][:30]:30} {str(m.get('name'))[:26]:26} {a['reason']}")
    if err:
        print("\nerrors:")
        for a in err[:15]:
            print(f"  {a['slug'][:30]:30} {a['error']}")


def shard_arg(text):
    """"i/k" -> (i, k), refusing anything that would silently select nothing."""
    try:
        i, k = (int(x) for x in text.split("/"))
    except ValueError:
        raise argparse.ArgumentTypeError(f"expected i/k, e.g. 0/4; got {text!r}")
    if k < 1 or not 0 <= i < k:
        raise argparse.ArgumentTypeError(f"need 0 <= i < k; got {text!r}")
    return i, k


def parse_args(argv=None):
    """Strict: an unknown or mistyped flag exits 2 here, before main() reads a
    key or sends a request. The old hand-rolled sys.argv checks ignored any flag
    they did not know, so `--dry-run` (which did not exist) ran a billed fetch."""
    ap = argparse.ArgumentParser(
        prog="fetch_google_ratings.py",
        description="Fetch Google Places ratings for each restaurant (billed).")
    ap.add_argument("--shard", type=shard_arg, default=(0, 1), metavar="i/k",
                    help="only every k-th restaurant, starting at i")
    ap.add_argument("--force", action="store_true",
                    help="re-fetch slugs that are already cached; this re-bills")
    ap.add_argument("--report", action="store_true",
                    help="summarise the cache and stop; no key, no network")
    ap.add_argument("--dry-run", action="store_true",
                    help="print what would be fetched and the estimated cost; "
                         "no key, no network")
    return ap.parse_args(argv)


def load_overrides():
    return (json.loads(OVERRIDES.read_text(encoding="utf-8")).get("place_ids", {})
            if OVERRIDES.exists() else {})


def plan(force, shard_i, shard_k):
    """-> (rows, todo): every target, and the ones this run would fetch."""
    rows = targets()
    todo = [r for n, r in enumerate(rows)
            if n % shard_k == shard_i
            and (force or not (OUT / f"{r[0]}.json").exists())]
    return rows, todo


def dry_run(force, shard_i, shard_k):
    """What a real run would fetch and cost, without the key or the network."""
    overrides = load_overrides()
    rows, todo = plan(force, shard_i, shard_k)
    pinned = sum(1 for r in todo if overrides.get(r[0]))
    print(f"shard {shard_i}/{shard_k}: {len(todo)} would be fetched "
          f"({len(rows)} total, {len(list(OUT.glob('*.json')))} cached) -- "
          f"{len(todo) - pinned} by Text Search, {pinned} by Details on a "
          f"hand-verified place_id.")
    print(f"estimated cost: ${len(todo) * TEXT_SEARCH_USD_PER_1000 / 1000:.2f} "
          f"at ${TEXT_SEARCH_USD_PER_1000:.0f}/1000 calls, billed once -- results "
          f"cache per slug. Dry run: no key read, nothing sent.")
    for slug, name, hood, boro, _lat, _lng in todo:
        pid = overrides.get(slug)
        print(f"  {slug[:30]:31} "
              + (f"(Details for hand-verified {pid})" if pid
                 else query_for(name, hood, boro)))


def main(argv=None):
    args = parse_args(argv)
    if args.report:
        return report()
    shard_i, shard_k = args.shard
    if args.dry_run:
        return dry_run(args.force, shard_i, shard_k)
    key = api_key()
    overrides = load_overrides()
    rows, todo = plan(args.force, shard_i, shard_k)
    print(f"shard {shard_i}/{shard_k}: {len(todo)} to fetch "
          f"({len(rows)} total, {len(list(OUT.glob('*.json')))} cached)", flush=True)
    for n, (slug, name, hood, boro, lat, lng) in enumerate(todo, 1):
        rec = fetch_one(slug, name, hood, boro, lat, lng, key, overrides.get(slug))
        write(rec)
        m = rec["matched"] or {}
        print(f"  [{n}/{len(todo)}] {slug}: "
              f"{'OK ' if rec['accepted'] else '-- '}"
              f"{m.get('rating', '?')}* {m.get('user_ratings_total', '?')} "
              f"{rec['reason'] or rec['error'] or ''}", flush=True)
        time.sleep(PAUSE)


if __name__ == "__main__":
    main()
