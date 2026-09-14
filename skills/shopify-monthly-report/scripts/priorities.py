"""
Priority engine.

Produces the 90-day plan: two or three workstreams, each with a measured target
and monthly milestones.

Three principles hold the whole thing up.

1. **No industry benchmark.** A priority rests on what a line is worth in
   money, on the store degrading against itself, or on a structural
   dependency. Never on "the market does better".

2. **Targets are calculated, not decreed.** A workstream aims at a level the
   store actually reached in the last six months. A level already reached is
   reachable, and that holds up in a meeting.

3. **The gain is arithmetic.** "Bringing the rate from 17.0% to 14.1% recovers
   1,109 per month at current volume" can be checked with a pencil. No
   workstream is proposed without that calculation.

The engine never says why an indicator moved, nor how to fix it. It says what
it costs, where to return to, and at what pace.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import Lang  # noqa: E402

# A workstream whose monthly gain is worth less than this against revenue does
# not make the plan: it is noise, and it would take a real subject's place.
GAIN_THRESHOLD = 0.02

# Window used as the internal reference. Six months: long enough to find a good
# level, short enough not to reach back to a period when the store worked
# differently.
WINDOW = 6

# Ceiling on ambition over 90 days when the reference level is old.
CAP = 0.30


def _milestones(current, target, n=3):
    return [current + (target - current) * (i + 1) / n for i in range(n)]


def _best(series, key, direction="min", ignore_zero=True):
    """
    Best level reached over the reference window, current month excluded.
    Returns (value, months_ago) or (None, None).

    `ignore_zero` drops months at exactly zero: on a return rate, a perfect
    zero almost always means no returns were being recorded at the time, not
    that the store was flawless. Keeping it as a target would produce an
    absurd goal.
    """
    window = series[-(WINDOW + 1):-1]
    candidates = []
    for i, row in enumerate(window):
        v = row.get(key)
        if v is None or (ignore_zero and v == 0):
            continue
        candidates.append((v, len(window) - i))
    if not candidates:
        return None, None
    return (min if direction == "min" else max)(candidates, key=lambda c: c[0])


def _target(current, best, months_ago, direction="min", cap=CAP):
    """
    Sets the goal between what the store has already done and what can
    reasonably be aimed at in 90 days.

    A level reached one or two months ago is taken as is: the proof it can be
    done is fresh. An older level is capped at `cap` relative improvement,
    otherwise a metric degrading for six months would produce a target nobody
    can hold. This came up in real conditions: a return rate that went from
    0.8% to 17% in eight months produced a 6.7% target, inherited from a month
    when returns were not yet all recorded.
    """
    if best is None:
        return None
    if months_ago is not None and months_ago <= 2:
        return best
    bound = current * (1 - cap) if direction == "min" else current * (1 + cap)
    return max(best, bound) if direction == "min" else min(best, bound)


def _kpis(data):
    return {k.get("key"): k for k in (data.get("kpis") or [])}


# ---------------------------------------------------------------------------
# workstreams
# ---------------------------------------------------------------------------

def _w_returns(data, L, cur, out):
    rt = data.get("returns") or {}
    sd = data.get("sales_detail") or {}
    rate, gross = rt.get("rate"), sd.get("gross_sales")
    if rate is None or not gross:
        return
    hist = (data.get("history") or {}).get("returns") or []
    series = [{"rate": (abs(h.get("reversals") or 0) / h["gross_sales"])
               if h.get("gross_sales") else None} for h in hist]
    best, months_ago = _best(series, "rate", "min")
    target = _target(rate, best, months_ago, "min")

    # A threshold the merchant declared beats the internal reference: they know
    # what they tolerate on their product. It stays capped at what 90 days allow.
    declared = (data.get("context") or {}).get("taux_retour_acceptable")
    if declared is None:
        declared = (data.get("context") or {}).get("acceptable_return_rate")
    from_client = False
    if declared is not None and declared < rate:
        floor = rate * (1 - CAP)
        if declared >= floor:
            target, from_client = declared, True
        elif target is None or floor < target:
            target = floor

    convention = target is None
    if convention:
        target = rate * 0.8
    if target >= rate:
        return

    capped = not convention and months_ago is not None and months_ago > 2
    ref = ("priorities.ref_declared" if from_client else
           "priorities.ref_convention" if convention else
           "priorities.ref_capped" if capped else "priorities.ref_best_six")
    gain = (rate - target) * gross
    out.append({
        "key": "returns", "nature": "leak",
        "title": L.t("priorities.titles.returns"),
        "finding": L.t("priorities.returns_finding",
                       amount=L.money(rt.get("amount") or 0, cur, True),
                       rate=L.pct(rate),
                       annual=L.money(abs(rt.get("amount") or 0) * 12, cur, True)),
        "goal": L.t("priorities.returns_goal", target=L.pct(target)),
        "reference": L.t(ref),
        "weight": gain * 12, "gain": gain, "unit": "rate",
        "current": rate, "target": target,
        "milestones": _milestones(rate, target)})


def _w_conversion(data, L, cur, out):
    k = _kpis(data)
    cr = (k.get("cr") or {}).get("value")
    aov = (k.get("aov") or {}).get("value")
    sessions = (data.get("funnel") or {}).get("sessions")
    if cr is None or not aov or not sessions:
        return
    hist = (data.get("history") or {}).get("conversion") or []
    series = [{"cr": h.get("conversion_rate")} for h in hist
              if (h.get("sessions") or 0) > 200]
    best, months_ago = _best(series, "cr", "max")
    target = _target(cr, best, months_ago, "max")
    if target is None or target <= cr:
        return
    gain = (target - cr) * sessions * aov
    out.append({
        "key": "conversion", "nature": "leak",
        "title": L.t("priorities.titles.conversion"),
        "finding": L.t("priorities.conversion_finding", rate=L.pct(cr, 2),
                       target=L.pct(target, 2)),
        "goal": L.t("priorities.conversion_goal", target=L.pct(target, 2)),
        "reference": L.t("priorities.ref_best_six" if months_ago and months_ago <= 2
                         else "priorities.ref_capped"),
        "weight": gain * 12, "gain": gain, "unit": "rate2",
        "current": cr, "target": target,
        "milestones": _milestones(cr, target),
        "note": L.t("priorities.conversion_note", sessions=L.num(sessions),
                    aov=L.money(aov, cur))})


def _w_margin(data, L, cur, out):
    mg = data.get("margin") or {}
    rate, net, ref = mg.get("margin_rate"), mg.get("net_sales"), \
        mg.get("compare_margin_rate")
    if rate is None or not net or ref is None or ref <= rate or ref - rate < 0.01:
        return
    gain = (ref - rate) * net
    out.append({
        "key": "margin", "nature": "leak",
        "title": L.t("priorities.titles.margin"),
        "finding": L.t("priorities.margin_finding", rate=L.pct(rate),
                       ref=L.pct(ref)),
        "goal": L.t("priorities.margin_goal", ref=L.pct(ref)),
        "reference": L.t("priorities.ref_period"),
        "weight": gain * 12, "gain": gain, "unit": "rate",
        "current": rate, "target": ref,
        "milestones": _milestones(rate, ref)})


def _w_basket(data, L, cur, out):
    k = _kpis(data)
    aov = k.get("aov") or {}
    value = aov.get("value")
    ref_key = next(iter(aov.get("compare") or {}), None)
    if value is None or not ref_key:
        return
    ref = (aov.get("compare") or {}).get(ref_key)
    orders = (k.get("orders") or {}).get("value")
    if not ref or not orders or ref <= value or (ref - value) / ref < 0.05:
        return
    gain = (ref - value) * orders
    out.append({
        "key": "basket", "nature": "leak",
        "title": L.t("priorities.titles.basket"),
        "finding": L.t("priorities.basket_finding", value=L.money(value, cur),
                       ref=L.money(ref, cur)),
        "goal": L.t("priorities.basket_goal", ref=L.money(ref, cur)),
        "reference": L.t("priorities.ref_period"),
        "weight": gain * 12, "gain": gain, "unit": "money",
        "current": value, "target": ref,
        "milestones": _milestones(value, ref)})


def _w_source_dependency(data, L, cur, out):
    src = data.get("traffic_sources") or []
    if len(src) < 2:
        return
    total = sum(s.get("sales") or 0 for s in src)
    if total <= 0:
        return
    head = src[0]
    share = (head.get("sales") or 0) / total
    if share < 0.55:
        return
    target = share - 0.05
    current_rest = total - (head.get("sales") or 0)
    goal_rest = (head.get("sales") or 0) * (1 - target) / target
    gain = goal_rest - current_rest
    if gain <= 0:
        return
    out.append({
        "key": "source_dependency", "nature": "risk",
        "title": L.t("priorities.titles.source_dependency"),
        "finding": L.t("priorities.source_finding", share=L.pct(share),
                       name=head["label"]),
        "goal": L.t("priorities.source_goal", target=L.pct(target)),
        "reference": L.t("priorities.ref_step"),
        "weight": gain * 12, "gain": gain, "unit": "rate",
        "current": share, "target": target,
        "milestones": _milestones(share, target),
        "note": L.t("priorities.source_note",
                    current=L.money(current_rest, cur, True),
                    goal=L.money(goal_rest, cur, True))})


def _w_catalogue_concentration(data, L, cur, out):
    tp = data.get("top_products") or []
    gross = (data.get("sales_detail") or {}).get("gross_sales")
    if len(tp) < 3 or not gross:
        return
    top3 = sum(p.get("sales") or 0 for p in tp[:3])
    share = top3 / gross
    if share < 0.60:
        return
    target = share - 0.05
    current_rest = gross - top3
    goal_rest = top3 * (1 - target) / target
    gain = goal_rest - current_rest
    if gain <= 0:
        return
    out.append({
        "key": "catalogue_concentration", "nature": "risk",
        "title": L.t("priorities.titles.catalogue_concentration"),
        "finding": L.t("priorities.concentration_finding", share=L.pct(share)),
        "goal": L.t("priorities.concentration_goal", target=L.pct(target)),
        "reference": L.t("priorities.ref_step"),
        "weight": gain * 12, "gain": gain, "unit": "rate",
        "current": share, "target": target,
        "milestones": _milestones(share, target),
        "note": L.t("priorities.concentration_note",
                    current=L.money(current_rest, cur, True),
                    goal=L.money(goal_rest, cur, True))})


WORKSTREAMS = [_w_conversion, _w_returns, _w_margin, _w_basket,
               _w_source_dependency, _w_catalogue_concentration]


def _fmt(L, value, unit, cur):
    if unit == "money":
        return L.money(value, cur)
    if unit == "rate2":
        return L.pct(value, 2)
    return L.pct(value)


def compute(data, limit=3, lang=None):
    """Return the retained workstreams, heaviest first."""
    meta = data.get("meta") or {}
    L = lang if isinstance(lang, Lang) else Lang(lang or meta.get("lang", "fr"))
    cur = meta.get("currency", "EUR")
    revenue = (_kpis(data).get("total_sales") or {}).get("value") or 0

    out = []
    for w in WORKSTREAMS:
        try:
            w(data, L, cur, out)
        except Exception:
            continue

    kept = [c for c in out if not revenue or c["gain"] >= revenue * GAIN_THRESHOLD]

    # Two natures that must never be ranked together. A leak is money walking
    # out that can be recovered; a risk is a dependency reduced by moving
    # revenue, not by earning it. Comparing their amounts would push a real
    # refund problem out of the plan in favour of a conventional
    # diversification target.
    leaks = sorted([c for c in kept if c["nature"] == "leak"],
                   key=lambda c: -c["gain"])
    risks = sorted([c for c in kept if c["nature"] == "risk"],
                   key=lambda c: -c["gain"])
    # At most one risk in the plan: beyond that it stops being actionable.
    plan = (leaks + risks[:1])[:limit]

    for i, c in enumerate(plan, start=1):
        c["rank"] = i
        c["weight_txt"] = L.money(c["weight"], cur, True)
        c["gain_txt"] = L.money(c["gain"], cur, True)
        c["milestones_txt"] = [_fmt(L, v, c["unit"], cur) for v in c["milestones"]]
        c["current_txt"] = _fmt(L, c["current"], c["unit"], cur)
        c["target_txt"] = _fmt(L, c["target"], c["unit"], cur)
        c["gain_label"] = L.t("labels.gain_develop" if c["nature"] == "risk"
                              else "labels.gain_monthly")
    return plan


def to_state(priorities, meta):
    """
    Condensed form of the plan, stored in the shop metafield so next month's
    report can measure the milestones. Keys are language-independent.
    """
    return {
        "period": meta.get("period_label"),
        "generated_on": meta.get("generated_on"),
        "workstreams": [{
            "key": c["key"],
            "title": c["title"],
            "unit": c["unit"],
            "current": c["current"],
            "target": c["target"],
            "milestones": c["milestones"],
            "monthly_gain": c["gain"],
        } for c in priorities],
    }


def follow_up(previous, data, lang=None):
    """
    Compares last month's milestones to what is measured this month. Returns
    one line per workstream, never qualifying the outcome.
    """
    if not previous:
        return []
    items = previous.get("workstreams") or previous.get("chantiers") or []
    if not items:
        return []
    meta = data.get("meta") or {}
    L = lang if isinstance(lang, Lang) else Lang(lang or meta.get("lang", "fr"))
    cur = meta.get("currency", "EUR")
    k = _kpis(data)
    measured = {
        "returns": (data.get("returns") or {}).get("rate"),
        "conversion": (k.get("cr") or {}).get("value"),
        "margin": (data.get("margin") or {}).get("margin_rate"),
        "basket": (k.get("aov") or {}).get("value"),
    }
    # Plans written before workstreams carried a stable key fall back on the
    # translated title, which only matches within one language.
    by_title = {L.t(f"priorities.titles.{key}"): key for key in measured}

    lines = []
    for c in items:
        key = c.get("key") or by_title.get(c.get("title") or c.get("titre"))
        value = measured.get(key)
        unit = c.get("unit") or c.get("unite") or "rate"
        milestones = c.get("milestones") or c.get("jalons") or []
        if value is None or not milestones:
            continue
        start = c.get("current", c.get("actuel"))
        target = c.get("target", c.get("cible", 0))
        going_down = target < (start or 0)
        met = value <= milestones[0] if going_down else value >= milestones[0]
        lines.append({
            "title": c.get("title") or c.get("titre") or key,
            "start": _fmt(L, start, unit, cur) if start is not None
            else L.t("common.na"),
            "milestone": _fmt(L, milestones[0], unit, cur),
            "measured": _fmt(L, value, unit, cur),
            "met": met})
    return lines


if __name__ == "__main__":
    import json
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    code = sys.argv[2] if len(sys.argv) > 2 else None
    for c in compute(d, lang=code):
        print(f"--- {c['rank']}. {c['title']}")
        print(f"    {c['finding']}")
        print(f"    weight: {c['weight_txt']} | gain: {c['gain_txt']}")
        print(f"    goal: {c['goal']} ({c['reference']})")
        print(f"    milestones: {' / '.join(c['milestones_txt'])}")
        if c.get("note"):
            print(f"    note: {c['note']}")
