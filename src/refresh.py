"""Weekly refresh: re-pull listing, fetch new details/menus, rebuild DB, diff.

Usage: python src/refresh.py [--force-menus] [--dry-run]
  --force-menus  re-download every PDF (detects in-place menu content changes;
                 otherwise only new/missing PDFs are fetched)
  --dry-run      run nothing but `fetch_google_ratings.py --dry-run`: the one
                 billed step's count and cost, with no key and no network
  An unknown argument is an error, raised before anything runs: this script
  bills Google Places whenever GOOGLE_PLACES_KEY is set.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parent


def run(script, *args):
    print(f"\n=== {script} {' '.join(args)} ===", flush=True)
    subprocess.run([sys.executable, str(SRC / script), *args], check=True)


def parse_args(argv=None):
    ap = argparse.ArgumentParser(
        prog="refresh.py",
        description="Weekly refresh (crawls; bills Google Places when "
                    "GOOGLE_PLACES_KEY is set).")
    ap.add_argument("--force-menus", action="store_true",
                    help="re-download every PDF and force a full re-parse")
    ap.add_argument("--dry-run", action="store_true",
                    help="preview only the billed ratings step; runs nothing else")
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.dry_run:
        # Against the CURRENT database: a real refresh rebuilds it first, so
        # restaurants new this week are not in this count yet.
        print("dry run: previewing the billed step only, against the current DB "
              "(a real refresh rebuilds it first). Nothing else runs.", flush=True)
        return run("fetch_google_ratings.py", "--dry-run")
    force = args.force_menus
    if force:
        menus = SRC.parent / "data" / "raw" / "menus"
        for f in menus.glob("*.pdf"):
            f.unlink()
        # parse_menus.py skips any slug already in parsed-progress.json, so
        # without clearing it the re-downloaded PDFs are never re-parsed and
        # in-place menu edits never reach the DB or the site -- which is the
        # entire reason --force-menus exists.
        progress = menus / "parsed-progress.json"
        if progress.exists():
            progress.unlink()
            print("cleared parsed-progress.json (forcing a full re-parse)")
    run("fetch_listing.py")
    run("fetch_details.py")
    run("download_menus.py")
    run("parse_menus.py")
    run("build_db.py")
    run("tag_dishes.py")          # build_db recreates the DB, so re-tag
    run("enrich_recognition.py")  # re-match from cached raw recognition files
    # Outdoor licences are issued and expire continuously, so unlike the subway
    # stations this is re-pulled -- one request a week against NYC Open Data.
    run("fetch_outdoor_dining.py", "--refresh")
    # Ratings drift slowly and the cache is keyed per slug, so this only calls
    # the API for restaurants added since last week -- usually zero. Skipped
    # entirely without a key, which is the case in CI: the key is gitignored
    # and must never be committed to a public repo.
    if os.environ.get("GOOGLE_PLACES_KEY"):
        run("fetch_google_ratings.py")
    else:
        print("fetch_google_ratings.py skipped: no GOOGLE_PLACES_KEY in env")
    # The venue roster is the site's spine: the award universe, with Restaurant
    # Week participation as one nullable column on it. It reads the rebuilt
    # restaurants table, so it must follow build_db; resolve_venues applies the
    # committed Places cache and needs no key (it only FETCHES with --fetch,
    # which is a manual, billed step -- see the README).
    run("build_venues.py")
    run("resolve_venues.py")
    run("export_venues.py")
    run("export_site_data.py")    # docs/ payload; must follow tag+recognition
    # The my-list payload shrinks its Google scores toward the ROSTER mean, so
    # it has to follow both the ratings fetch and the exporter it borrows from.
    run("export_places.py")
    run("diff_report.py")


if __name__ == "__main__":
    main()
