#!/usr/bin/env python3
"""
Builds skills/trente/assets/fr-departments.json, the map of France the
`map_fr` view draws: department outlines, names and populations.

    python3 tools/build_fr_map.py

Sources, both open data:

- Outlines: IGN Admin Express COG, as simplified by gregoiredavid/france-geojson
  (Licence Ouverte / Etalab).
- Populations: INSEE, populations de référence (population municipale), read
  from the Melodi API.

The script downloads both, projects each frame on its own (metropolitan France,
the Île-de-France inset and one inset per overseas department), simplifies the
outlines and rounds them to integers, so the asset stays small enough for the
plugin directory. It is run by hand when a new population year comes out; the
plugin only reads its output.
"""

import json
import math
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "skills", "trente", "assets", "fr-departments.json")

GEOJSON = ("https://raw.githubusercontent.com/gregoiredavid/france-geojson/"
           "master/departements-avec-outre-mer.geojson")
POP_YEAR = "2023"
POPULATION = ("https://api.insee.fr/melodi/data/DS_POPULATIONS_REFERENCE"
              f"?GEO=DEP&POPREF_MEASURE=PMUN&TIME_PERIOD={POP_YEAR}&maxResult=500")

IDF = ["75", "77", "78", "91", "92", "93", "94", "95"]
OVERSEAS = ["971", "972", "973", "974", "976"]

# Frame name -> (departments, simplification tolerance, smallest ring kept),
# both in frame units, the longest side of a frame being SIZE units.
SIZE = 1000
FRAMES = {
    "metro": (None, 1.1, 6.0),
    "idf": (IDF, 0.9, 4.0),
    **{code: ([code], 1.6, 20.0) for code in OVERSEAS},
}


def fetch(url):
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def rings(geometry):
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"][0]]
    return [poly[0] for poly in geometry["coordinates"]]


def simplify(points, tol):
    """Douglas-Peucker on a list of (x, y), with an explicit stack."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        i, j = stack.pop()
        a, b = points[i], points[j]
        dx, dy = b[0] - a[0], b[1] - a[1]
        norm = math.hypot(dx, dy) or 1e-12
        far, idx = 0.0, None
        for k in range(i + 1, j):
            p = points[k]
            d = abs(dy * (p[0] - a[0]) - dx * (p[1] - a[1])) / norm
            if d > far:
                far, idx = d, k
        if idx is not None and far > tol:
            keep[idx] = True
            stack += [(i, idx), (idx, j)]
    return [p for p, k in zip(points, keep) if k]


def area(points):
    return abs(sum(points[i][0] * points[i - 1][1] - points[i - 1][0] * points[i][1]
                   for i in range(len(points)))) / 2


def frame(features, codes, tol, min_area):
    chosen = {c: f for c, f in features.items() if c in codes}
    lon = [p[0] for f in chosen.values() for r in rings(f["geometry"]) for p in r]
    lat = [p[1] for f in chosen.values() for r in rings(f["geometry"]) for p in r]
    x0, x1, y0, y1 = min(lon), max(lon), min(lat), max(lat)
    k = math.cos(math.radians((y0 + y1) / 2))
    w, h = (x1 - x0) * k, y1 - y0
    scale = SIZE / max(w, h)
    shapes = {}
    for code, f in sorted(chosen.items()):
        out = []
        for ring in rings(f["geometry"]):
            pts = [((x - x0) * k * scale, (y1 - y) * scale) for x, y in ring]
            # Simplify the ring as two halves, so its closing point survives.
            half = len(pts) // 2
            pts = simplify(pts[:half + 1], tol)[:-1] + simplify(pts[half:], tol)
            if len(pts) < 4 or area(pts) < min_area:
                continue
            flat = []
            for x, y in pts:
                flat += [round(x), round(y)]
            out.append(flat)
        if not out:  # never lose a department to the area threshold
            ring = max(rings(f["geometry"]), key=len)
            flat = []
            for x, y in ring[::max(1, len(ring) // 12)]:
                flat += [round((x - x0) * k * scale), round((y1 - y) * scale)]
            out.append(flat)
        shapes[code] = out
    return {"w": round(w * scale), "h": round(h * scale), "shapes": shapes}


def main():
    geo = fetch(GEOJSON)
    features = {f["properties"]["code"]: f for f in geo["features"]}
    names = {c: f["properties"]["nom"] for c, f in sorted(features.items())}
    metro = [c for c in features if not c.startswith("97")]

    pop = fetch(POPULATION)
    population = {}
    for obs in pop["observations"]:
        code = obs["dimensions"]["GEO"].rsplit("-", 1)[-1]
        population[code] = int(obs["measures"]["OBS_VALUE_NIVEAU"]["value"])

    frames = {}
    for name, (codes, tol, min_area) in FRAMES.items():
        frames[name] = frame(features, codes or metro, tol, min_area)

    asset = {
        "sources": {
            "outlines": "IGN, Admin Express COG, via gregoiredavid/france-geojson "
                        "(Licence Ouverte)",
            "population": f"INSEE, populations de référence {POP_YEAR}, "
                          "population municipale",
            "population_year": POP_YEAR,
        },
        "names": names,
        "population": dict(sorted(population.items())),
        "frames": frames,
    }
    missing = sorted(set(names) - set(population))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(asset, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    points = sum(len(r) // 2 for fr in frames.values()
                 for s in fr["shapes"].values() for r in s)
    print(f"{OUT}: {os.path.getsize(OUT) / 1024:.0f} KB, {points} points, "
          f"{len(names)} departments, no population for: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
