"""Borough outlines for the roster's map view, small enough to commit.

Usage: python src/fetch_borough_outlines.py [--from-file saved.geojson]

The roster page (docs/index.html) allows no third-party origin at all --
no tile server, no CDN -- which rules out every off-the-shelf map. What a
dot map actually needs from a basemap is one recognisable shape: the five
boroughs' coastline. This script turns NYC Planning's borough-boundary
polygons (ArcGIS FeatureServer, public data, ~3 MB) into docs/data/
boroughs.json (~tens of KB): Douglas-Peucker simplified, small islands
dropped, coordinates rounded to 4 decimals (~11 m), which is far below
what a city-scale outline can show.

Committed because it changes only when the city's shoreline does.
"""
import json
import sys
import urllib.request

sys.setrecursionlimit(100000)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "data" / "boroughs.json"
URL = ("https://services5.arcgis.com/GfwWNkhOj9bNBqoJ/arcgis/rest/services/"
       "NYC_Borough_Boundary/FeatureServer/0/query"
       "?where=1%3D1&outFields=BoroName&outSR=4326&f=geojson")

# Degrees. ~0.0006 is ~60 m N-S: invisible at page scale, and together with
# the island floor it is what turns 81,000 points into a few thousand.
TOLERANCE = 0.0006
# Rings whose bounding box spans less than this are dropped -- piers, rocks,
# marsh islets. Roosevelt, Governors, City and Rikers Islands all clear it.
MIN_RING_SPAN = 0.006


def simplify(ring, tol):
    """Douglas-Peucker on a closed ring (first point == last)."""
    def dp(pts):
        if len(pts) < 3:
            return pts
        (x1, y1), (x2, y2) = pts[0], pts[-1]
        dx, dy = x2 - x1, y2 - y1
        den = (dx * dx + dy * dy) ** 0.5 or 1e-12
        imax, dmax = 0, -1.0
        for i in range(1, len(pts) - 1):
            x0, y0 = pts[i]
            d = abs(dx * (y1 - y0) - (x1 - x0) * dy) / den
            if d > dmax:
                imax, dmax = i, d
        if dmax <= tol:
            return [pts[0], pts[-1]]
        left, right = dp(pts[:imax + 1]), dp(pts[imax:])
        return left[:-1] + right
    # A closed ring's endpoints are the same point, so the baseline dp()
    # measures against has zero length and every distance reads as zero --
    # the whole ring "simplifies" to nothing. Split it into two arcs between
    # two far-apart anchors and simplify each arc on its own.
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    a = max(range(len(pts)), key=lambda i: pts[i])
    rot = pts[a:] + pts[:a + 1]                     # closed, starts at anchor a
    b = max(range(len(rot)),
            key=lambda i: (rot[i][0] - rot[0][0]) ** 2 + (rot[i][1] - rot[0][1]) ** 2)
    out = dp(rot[:b + 1])[:-1] + dp(rot[b:])
    return out


def main():
    if "--from-file" in sys.argv:
        raw = Path(sys.argv[sys.argv.index("--from-file") + 1]).read_bytes()
    else:
        req = urllib.request.Request(URL, headers={
            "User-Agent": "nyc-restaurant-week-roster/1.0 "
                          "(github.com/Kejjeh/nyc-restaurants)"})
        raw = urllib.request.urlopen(req, timeout=60).read()
    src = json.loads(raw)

    boroughs, pts_in, pts_out = [], 0, 0
    for f in src["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        rings = []
        for poly in polys:
            outer = poly[0]           # holes are inland waters; the map skips them
            pts_in += len(outer)
            xs = [p[0] for p in outer]
            ys = [p[1] for p in outer]
            if max(xs) - min(xs) < MIN_RING_SPAN and max(ys) - min(ys) < MIN_RING_SPAN:
                continue
            slim = [[round(x, 4), round(y, 4)]
                    for x, y in simplify([tuple(p) for p in outer], TOLERANCE)]
            deduped = [p for i, p in enumerate(slim) if not i or p != slim[i - 1]]
            if len(deduped) >= 4:
                pts_out += len(deduped)
                rings.append(deduped)
        boroughs.append({"name": f["properties"]["BoroName"], "rings": rings})

    boroughs.sort(key=lambda b: b["name"])
    doc = {
        "_doc": "Five-borough shoreline for the roster map, simplified from "
                "NYC Planning's borough boundaries (ArcGIS FeatureServer, "
                "public data) by src/fetch_borough_outlines.py. Coordinates "
                "are [lng, lat] to 4 decimals; small islands dropped.",
        "boroughs": boroughs,
    }
    OUT.write_text(json.dumps(doc, separators=(",", ":")), encoding="utf-8")
    print(f"{pts_in} points in, {pts_out} out; "
          f"{OUT.stat().st_size / 1024:.0f} KB -> {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
