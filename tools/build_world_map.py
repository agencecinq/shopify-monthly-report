#!/usr/bin/env python3
"""
Builds skills/trente/assets/world-countries.json, the world map the
`map_world` view draws: country outlines, names and populations.

    python3 tools/build_world_map.py

Sources:

- Outlines: Natural Earth, Admin 0 countries at 1:50m (public domain).
- Populations: World Bank, SP.POP.TOTL, latest year (CC BY 4.0).

Two frames: the world in the Equal Earth projection, which keeps areas true,
without Antarctica; and Europe, clipped to a box and drawn larger, where small
countries would otherwise vanish. Run by hand when the sources move on; the
plugin only reads the output.
"""

import json
import math
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_fr_map import area, simplify  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "skills", "trente", "assets", "world-countries.json")

COUNTRIES = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
             "master/geojson/ne_50m_admin_0_countries.geojson")
POPULATION = ("https://api.worldbank.org/v2/country/all/indicator/SP.POP.TOTL"
              "?mrnev=1&format=json&per_page=400")

# Natural Earth draws a few de facto territories apart. Shopify knows only the
# ISO country, so they are drawn as part of it.
FOLD = {"Somaliland": "SO", "N. Cyprus": "CY", "Siachen Glacier": "IN"}
DROP = {"AQ"}

SIZE = 1000
EUROPE = (-25.0, 34.0, 42.0, 71.5)   # lon min, lat min, lon max, lat max


def fetch(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def rings(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    return [poly[0] for poly in geometry["coordinates"]]


def equal_earth(lon, lat):
    """Equal Earth projection (Šavrič, Patterson and Jenny, 2018)."""
    a1, a2, a3, a4 = 1.340264, -0.081106, 0.000893, 0.003796
    lam, phi = math.radians(lon), math.radians(lat)
    theta = math.asin(math.sqrt(3) / 2 * math.sin(phi))
    t2, t6 = theta ** 2, theta ** 6
    x = 2 * math.sqrt(3) * lam * math.cos(theta) / (
        3 * (9 * a4 * t6 * t2 + 7 * a3 * t6 + 3 * a2 * t2 + a1))
    y = theta * (a1 + a2 * t2 + t6 * (a3 + a4 * t2))
    return x, -y


def clip(ring, box):
    """Sutherland-Hodgman: the part of a ring inside a lon/lat box."""
    x0, y0, x1, y1 = box
    edges = [(lambda p: p[0] >= x0, lambda a, b: _at_x(a, b, x0)),
             (lambda p: p[0] <= x1, lambda a, b: _at_x(a, b, x1)),
             (lambda p: p[1] >= y0, lambda a, b: _at_y(a, b, y0)),
             (lambda p: p[1] <= y1, lambda a, b: _at_y(a, b, y1))]
    pts = list(ring)
    for inside, cut in edges:
        if not pts:
            break
        out = []
        prev = pts[-1]
        for cur in pts:
            if inside(cur):
                if not inside(prev):
                    out.append(cut(prev, cur))
                out.append(cur)
            elif inside(prev):
                out.append(cut(prev, cur))
            prev = cur
        pts = out
    return pts


def _at_x(a, b, x):
    t = (x - a[0]) / (b[0] - a[0])
    return (x, a[1] + t * (b[1] - a[1]))


def _at_y(a, b, y):
    t = (y - a[1]) / (b[1] - a[1])
    return (a[0] + t * (b[0] - a[0]), y)


def build_frame(shapes_lonlat, project, tol, min_area):
    projected = {c: [[project(x, y) for x, y in r] for r in rs]
                 for c, rs in shapes_lonlat.items()}
    xs = [p[0] for rs in projected.values() for r in rs for p in r]
    ys = [p[1] for rs in projected.values() for r in rs for p in r]
    x0, y0 = min(xs), min(ys)
    scale = SIZE / max(max(xs) - x0, max(ys) - y0)
    shapes = {}
    for code, rs in sorted(projected.items()):
        out = []
        for r in rs:
            pts = [((x - x0) * scale, (y - y0) * scale) for x, y in r]
            half = len(pts) // 2
            pts = simplify(pts[:half + 1], tol)[:-1] + simplify(pts[half:], tol)
            if len(pts) < 4 or area(pts) < min_area:
                continue
            out.append([v for x, y in pts for v in (round(x), round(y))])
        if not out:  # a micro-state still gets a dot
            r = max(rs, key=len)
            cx = sum(p[0] for p in r) / len(r)
            cy = sum(p[1] for p in r) / len(r)
            cx, cy = round((cx - x0) * scale), round((cy - y0) * scale)
            out.append([cx - 2, cy - 2, cx + 2, cy - 2, cx + 2, cy + 2, cx - 2, cy + 2])
        shapes[code] = out
    return {"w": round((max(xs) - x0) * scale), "h": round((max(ys) - y0) * scale),
            "shapes": shapes}


def main():
    geo = fetch(COUNTRIES)
    shapes, names_en, names_fr, iso3 = {}, {}, {}, {}
    for f in geo["features"]:
        p = f["properties"]
        code = FOLD.get(p["NAME"]) or p["ISO_A2_EH"]
        if code in DROP or not code or code == "-99":
            continue
        shapes.setdefault(code, []).extend(rings(f["geometry"]))
        if p["NAME"] not in FOLD:
            names_en.setdefault(code, p["NAME_EN"])
            names_fr.setdefault(code, p["NAME_FR"])
            iso3.setdefault(p["ISO_A3_EH"] if p["ISO_A3_EH"] != "-99" else
                            {"XK": "XKX"}.get(code, ""), code)

    wb = fetch(POPULATION)[1]
    population, years = {}, set()
    for row in wb:
        code = iso3.get(row["countryiso3code"])
        if code and row["value"]:
            population[code] = int(row["value"])
            years.add(row["date"])

    europe = {}
    for code, rs in shapes.items():
        kept = [c for c in (clip(r, EUROPE) for r in rs) if len(c) >= 4]
        if kept:
            europe[code] = kept
    k = math.cos(math.radians(52))

    frames = {
        "world": build_frame(shapes, equal_earth, 0.9, 1.5),
        "europe": build_frame(europe, lambda x, y: (x * k, -y), 1.0, 3.0),
    }
    asset = {
        "sources": {
            "outlines": "Natural Earth, Admin 0 countries 1:50m (public domain)",
            "population": "World Bank, SP.POP.TOTL (CC BY 4.0)",
            "population_year": max(years) if years else None,
        },
        "names": {"en": dict(sorted(names_en.items())),
                  "fr": dict(sorted(names_fr.items()))},
        "population": dict(sorted(population.items())),
        "frames": frames,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(asset, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    points = sum(len(r) // 2 for fr in frames.values()
                 for s in fr["shapes"].values() for r in s)
    missing = sorted(set(names_en) - set(population))
    print(f"{OUT}: {os.path.getsize(OUT) / 1024:.0f} KB, {points} points, "
          f"{len(names_en)} countries, {len(europe)} in the Europe frame, "
          f"population {asset['sources']['population_year']}, "
          f"none for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
