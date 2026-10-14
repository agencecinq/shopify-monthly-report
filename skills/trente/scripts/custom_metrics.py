"""
Permanent metrics: the views a merchant asked to see in every report.

A metric is a recipe stored in the shop metafield, under
`context.custom_metrics`. It names the queries to run, the view to draw and the
columns to read. Each month Claude runs the queries verbatim for the period and
copies the rows they return into report.json, under the metric's `data`. This
module turns those rows into what a slide shows.

It computes nothing that is not in the rows, apart from the per-capita rate of
the map, which divides by the INSEE populations bundled with the plugin.

    python3 custom_metrics.py --check context.json

checks the recipes of a context, or of a report.json, before they are saved.
"""

import json
import os
import re
import sys

VIEWS = ("kpi", "bars", "table", "map_fr", "map_world")
UNITS = ("number", "money", "percent")
KINDS = ("flow", "stock")
TOOLS = ("run-analytics-query", "graphql_query")
MAX_METRICS = 8
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "assets")
ASSET = os.path.join(ASSETS, "fr-departments.json")
WORLD_ASSET = os.path.join(ASSETS, "world-countries.json")

# Shopify gives the overseas departments their own country codes.
OVERSEAS_COUNTRIES = {"GP": "971", "MQ": "972", "GF": "973", "RE": "974",
                      "YT": "976"}
# Postal codes in the 971 range that belong to overseas collectivities, not to
# Guadeloupe: Saint-Barthélemy and Saint-Martin.
NOT_GUADELOUPE = ("97133", "97150")


class MetricError(ValueError):
    """A metric this month's data cannot draw. The slide is left out."""


_assets = {}


def _load(path):
    if path not in _assets:
        with open(path, encoding="utf-8") as f:
            _assets[path] = json.load(f)
    return _assets[path]


def france():
    """The map of France: outlines, names and populations, loaded once."""
    return _load(ASSET)


def world():
    """The world map: outlines, names in English and French, populations."""
    return _load(WORLD_ASSET)


# ---------------------------------------------------------------------------
# recipes
# ---------------------------------------------------------------------------

def _refs(recipe):
    """Every {query, field} reference a recipe's view reads."""
    view = recipe.get("view")
    if view == "kpi":
        out = []
        for spec in [recipe.get("value")] + [d.get("value") for d in
                                             recipe.get("details") or []]:
            if isinstance(spec, dict) and "num" in spec:
                out += [spec.get("num"), spec.get("den")]
            else:
                out.append(spec)
        return out
    if view in ("bars", "table"):
        return [recipe.get("rows")]
    if view in ("map_fr", "map_world"):
        return [recipe.get("map")]
    return []


def validate(recipe):
    """Problems that would stop a recipe from being drawn, as sentences."""
    errors = []
    rid = recipe.get("id")
    if not isinstance(rid, str) or not ID_RE.match(rid):
        errors.append(f"id {rid!r}: lowercase letters, digits and hyphens only")
    name = rid or "?"
    for key in ("title", "request", "added"):
        if not recipe.get(key):
            errors.append(f"{name}: `{key}` is missing")
    if recipe.get("view") not in VIEWS:
        errors.append(f"{name}: view must be one of {', '.join(VIEWS)}")
    if recipe.get("unit", "number") not in UNITS:
        errors.append(f"{name}: unit must be one of {', '.join(UNITS)}")
    kind = recipe.get("kind")
    if kind not in KINDS:
        errors.append(f"{name}: kind must be one of {', '.join(KINDS)}")
    queries = recipe.get("queries") or []
    if not queries:
        errors.append(f"{name}: no query")
    names = set()
    for q in queries:
        qn = q.get("name")
        if not qn or qn in names:
            errors.append(f"{name}: every query needs a distinct `name`")
        names.add(qn)
        if q.get("tool") not in TOOLS:
            errors.append(f"{name}: query {qn!r} uses an unknown tool "
                          f"{q.get('tool')!r}")
        text = q.get("query") or ""
        if not text.strip():
            errors.append(f"{name}: query {qn!r} is empty")
        elif kind == "flow" and q.get("tool") == "run-analytics-query" and not (
                "START" in text and "END" in text):
            errors.append(f"{name}: query {qn!r} must read the period through "
                          "START and END")
    for ref in _refs(recipe):
        if not isinstance(ref, dict) or not ref.get("query") or not ref.get("field"):
            errors.append(f"{name}: the view needs a `query` and a `field`")
        elif ref["query"] not in names:
            errors.append(f"{name}: the view reads query {ref['query']!r}, "
                          "which the recipe does not define")
    if recipe.get("view") in ("bars", "table") and not (recipe.get("rows") or {}).get("label"):
        errors.append(f"{name}: a {recipe.get('view')} view needs a `label` column")
    if recipe.get("view") == "map_fr" and not (recipe.get("map") or {}).get("postal"):
        errors.append(f"{name}: a map of France needs a `postal` column")
    if recipe.get("view") == "map_world" and not (recipe.get("map") or {}).get("country"):
        errors.append(f"{name}: a world map needs a `country` column")
    return errors


def validate_all(recipes):
    errors = []
    if len(recipes) > MAX_METRICS:
        errors.append(f"{len(recipes)} permanent metrics, the deck holds "
                      f"{MAX_METRICS} at most")
    seen = set()
    for r in recipes:
        if r.get("id") in seen:
            errors.append(f"id {r.get('id')!r} is used twice")
        seen.add(r.get("id"))
        errors += validate(r)
    return errors


# ---------------------------------------------------------------------------
# reading rows
# ---------------------------------------------------------------------------

def _num(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def rows(metric, query):
    """The rows a query returned, as a list of objects keyed by column."""
    got = (metric.get("data") or {}).get(query)
    if isinstance(got, dict):
        got = got.get("rows") if "rows" in got else [got]
    if not isinstance(got, list):
        raise MetricError(f"no rows for query {query!r}")
    return [r for r in got if isinstance(r, dict)]


def _sum(metric, query, field):
    vals = [_num(r.get(field)) for r in rows(metric, query)]
    vals = [v for v in vals if v is not None]
    return sum(vals) if vals else None


def _value(metric, spec, compare=False):
    """
    A figure from a reference: the sum of a column, or the ratio of two.
    With `compare`, reads the reference's `compare_field` instead.
    """
    if "num" in spec:
        num = _value(metric, spec["num"], compare)
        den = _value(metric, spec["den"], compare)
        return num / den if num is not None and den else None
    field = spec.get("compare_field") if compare else spec.get("field")
    if not field:
        return None
    return _sum(metric, spec["query"], field)


def _at_least(metric, spec):
    """True when a count came back as a lower bound (customersCount past 10,000)."""
    specs = [spec["num"], spec["den"]] if "num" in spec else [spec]
    for s in specs:
        for r in rows(metric, s["query"]):
            if r.get("precision") not in (None, "EXACT"):
                return True
    return False


def _unit(metric, spec):
    return "percent" if "num" in spec else metric.get("unit", "number")


# ---------------------------------------------------------------------------
# departments
# ---------------------------------------------------------------------------

def department(postal, country=None):
    """
    The department code of a French postal code, or None when the address is
    outside the departments on the map (abroad, Monaco, an overseas
    collectivity, a malformed code).

    Corsica shares the 20 prefix: 20000 to 20199 is Corse-du-Sud, 20200 and
    up is Haute-Corse.
    """
    country = (country or "FR").strip().upper()
    if country in OVERSEAS_COUNTRIES and not postal:
        return OVERSEAS_COUNTRIES[country]
    if country not in ("FR", "FRANCE") and country not in OVERSEAS_COUNTRIES:
        return None
    digits = re.sub(r"\s", "", str(postal or ""))
    if not re.fullmatch(r"\d{5}", digits):
        return None
    if digits.startswith("97"):
        if digits in NOT_GUADELOUPE:
            return None
        code = digits[:3]
        return code if code in OVERSEAS_COUNTRIES.values() else None
    if digits.startswith("98") or digits.startswith("00"):
        return None
    if digits.startswith("20"):
        return "2A" if int(digits[:3]) < 202 else "2B"
    code = digits[:2]
    return code if code in france()["names"] else None


def by_department(metric, spec):
    """Sums the value column, and its comparison, per department."""
    cur, ref, outside, outside_ref = {}, {}, 0.0, 0.0
    for r in rows(metric, spec["query"]):
        dep = department(r.get(spec["postal"]), r.get(spec.get("country") or ""))
        v = _num(r.get(spec["field"])) or 0.0
        c = _num(r.get(spec["compare_field"])) if spec.get("compare_field") else None
        if dep is None:
            outside += v
            outside_ref += c or 0.0
            continue
        cur[dep] = cur.get(dep, 0.0) + v
        if c is not None:
            ref[dep] = ref.get(dep, 0.0) + c
    return cur, ref, outside


def classes(values, n=5):
    """
    Upper bounds of `n` classes holding about as many departments each.
    Quantiles keep every shade in use; equal steps would leave most of France
    in the palest one as soon as a single department stands out.
    """
    vals = sorted(v for v in values if v is not None and v > 0)
    if not vals:
        return []
    bounds = []
    for i in range(1, n + 1):
        b = vals[min(len(vals) - 1, round(i * len(vals) / n) - 1)]
        if not bounds or b > bounds[-1]:
            bounds.append(b)
    return bounds


def class_of(v, bounds):
    """0 for nothing, 1 to len(bounds) for a positive value, None without data."""
    if v is None:
        return None
    if v <= 0 or not bounds:
        return 0
    for i, b in enumerate(bounds):
        if v <= b:
            return i + 1
    return len(bounds)


# ---------------------------------------------------------------------------
# what a slide shows
# ---------------------------------------------------------------------------

def _delta(cur, ref):
    if cur is None or not ref:
        return None
    return (cur - ref) / abs(ref)


def _kpi(metric):
    spec = metric["value"]
    value = _value(metric, spec)
    if value is None:
        raise MetricError("the value column holds no number")
    if metric["kind"] == "stock":
        last = metric.get("last") or {}
        compare = _num(last.get("value"))
        basis = ("last_report", last.get("label") or last.get("period"))
    else:
        compare, basis = _value(metric, spec, compare=True), ("previous_period", None)
    details = []
    for d in (metric.get("details") or [])[:3]:
        try:
            v = _value(metric, d["value"])
        except MetricError:
            v = None
        if v is None:
            continue
        c = _value(metric, d["value"], compare=True)
        details.append({"label": d.get("label", ""), "value": v,
                        "unit": d.get("unit") or _unit(metric, d["value"]),
                        "compare": c, "delta": _delta(v, c)})
    return {"value": value, "unit": _unit(metric, spec), "at_least": _at_least(metric, spec),
            "compare": compare, "delta": _delta(value, compare), "basis": basis,
            "details": details}


def _rows(metric):
    spec = metric["rows"]
    out = []
    for r in rows(metric, spec["query"]):
        label = r.get(spec["label"])
        v = _num(r.get(spec["field"]))
        if label in (None, "") or v is None:
            continue
        c = _num(r.get(spec["compare_field"])) if spec.get("compare_field") else None
        out.append({"label": str(label), "value": v, "compare": c,
                    "delta": _delta(v, c)})
    if not out:
        raise MetricError("no row with both a label and a value")
    out.sort(key=lambda x: -x["value"])
    return {"rows": out[:int(spec.get("limit") or 10)],
            "label_title": spec.get("label_title"),
            "unit": metric.get("unit", "number")}


def _map(metric):
    spec = metric["map"]
    fr = france()
    cur, ref, outside = by_department(metric, spec)
    if not cur:
        raise MetricError("no row matched a French department")
    per_capita = spec.get("per_capita", True)
    pop = fr["population"]
    deps = {}
    for code, name in fr["names"].items():
        v = cur.get(code, 0.0)
        c = ref.get(code) if spec.get("compare_field") else None
        if per_capita:
            rate = v / pop[code] * 100000 if code in pop else None
        else:
            rate = v
        deps[code] = {"code": code, "names": {"fr": name}, "value": v, "rate": rate,
                      "compare": c, "delta": _delta(v, c)}
    bounds = classes([d["rate"] for d in deps.values()])
    for d in deps.values():
        d["class"] = class_of(d["rate"], bounds)
    ranked = sorted((d for d in deps.values() if d["rate"] is not None and d["value"] > 0),
                    key=lambda d: (-d["rate"], d["code"]))
    covered = [d for d in deps.values() if d["rate"] is not None]
    total = sum(d["value"] for d in covered)
    national = (total / sum(pop[d["code"]] for d in covered) * 100000
                if per_capita and covered else None)
    return {"areas": deps, "bounds": bounds, "top": ranked[:10],
            "per_capita": per_capita, "national": national,
            "mapped": sum(cur.values()), "outside": outside,
            "no_population": sorted(c for c in fr["names"] if c not in pop),
            "population_year": fr["sources"]["population_year"],
            "measure": spec.get("measure"),
            "unit": metric.get("unit", "number")}


def country(code):
    """
    The country a Shopify country code is drawn as, or None when the map does
    not have it. Shopify gives the overseas departments their own codes; the
    world map draws them as part of France, as Natural Earth does.
    """
    code = (code or "").strip().upper()
    if code in OVERSEAS_COUNTRIES:
        code = "FR"
    return code if code in world()["names"]["en"] else None


def _map_world(metric):
    spec = metric["map"]
    wm = world()
    cur, ref, outside = {}, {}, 0.0
    for r in rows(metric, spec["query"]):
        code = country(r.get(spec["country"]))
        v = _num(r.get(spec["field"])) or 0.0
        if code is None:
            outside += v
            continue
        cur[code] = cur.get(code, 0.0) + v
        if spec.get("compare_field"):
            c = _num(r.get(spec["compare_field"]))
            if c is not None:
                ref[code] = ref.get(code, 0.0) + c
    if not cur:
        raise MetricError("no row matched a country on the map")
    per_capita = spec.get("per_capita", False)
    pop = wm["population"]
    areas = {}
    for code in wm["names"]["en"]:
        v = cur.get(code, 0.0)
        c = ref.get(code) if spec.get("compare_field") else None
        if per_capita:
            rate = v / pop[code] * 1000000 if code in pop else None
        else:
            rate = v
        areas[code] = {"code": code,
                       "names": {lg: wm["names"][lg][code] for lg in wm["names"]},
                       "value": v, "rate": rate, "compare": c, "delta": _delta(v, c)}
    bounds = classes([a["rate"] for a in areas.values()])
    for a in areas.values():
        a["class"] = class_of(a["rate"], bounds)
    ranked = sorted((a for a in areas.values() if a["rate"] is not None and a["value"] > 0),
                    key=lambda a: (-a["rate"], -a["value"], a["code"]))
    return {"areas": areas, "bounds": bounds, "top": ranked[:10],
            "per_capita": per_capita, "national": None,
            "countries": sum(1 for v in cur.values() if v > 0),
            "mapped": sum(cur.values()), "outside": outside,
            "no_population": sorted(c for c in cur if c not in pop) if per_capita else [],
            "population_year": wm["sources"]["population_year"],
            "measure": spec.get("measure"),
            "unit": metric.get("unit", "number")}


def prepare(metric):
    """
    The view model of one metric from its recipe and this month's rows.
    Raises MetricError when the rows cannot be drawn.
    """
    problems = validate(metric)
    if problems:
        raise MetricError("; ".join(problems))
    view = metric["view"]
    model = {"id": metric["id"], "title": metric["title"], "view": view,
             "added": metric["added"], "kind": metric["kind"],
             "source": metric.get("source")}
    if view == "kpi":
        model.update(_kpi(metric))
    elif view in ("bars", "table"):
        model.update(_rows(metric))
    elif view == "map_fr":
        model.update(_map(metric))
    else:
        model.update(_map_world(metric))
    return model


def last_values(models, period, label):
    """
    What to store back on each stock metric, so next month's report can show
    the change: {id: {"period": "YYYY-MM", "label": ..., "value": ...}}.
    """
    return {m["id"]: {"period": period, "label": label, "value": m["value"]}
            for m in models if m.get("kind") == "stock" and m.get("view") == "kpi"}


def main():
    if len(sys.argv) != 3 or sys.argv[1] != "--check":
        sys.exit("usage: custom_metrics.py --check context.json")
    with open(sys.argv[2], encoding="utf-8") as f:
        doc = json.load(f)
    recipes = doc.get("custom_metrics") or (doc.get("context") or {}).get("custom_metrics") or []
    errors = validate_all(recipes)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    print(json.dumps({"metrics": len(recipes), "errors": errors}, ensure_ascii=False))
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
