"""
Priority engine.

Produces next month's plan: two or three workstreams, each with a target set
for the coming month. Next month's report measures that same target, so every
commitment the plan makes is checked once, a month later.

Three principles hold the whole thing up.

1. **No industry benchmark.** A priority rests on what a line is worth in
   money, on the store degrading against itself, or on a structural
   dependency. Never on "the market does better".

2. **Targets are calculated, and say where they come from.** Where the store
   has a monthly history, a workstream aims at a level it actually reached in
   the last six months, capped at what one month allows. Elsewhere the target is
   the reference period, a threshold the merchant declared, or a stated
   convention, and the slide names which one.

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
from shared import source_share, top3_share  # noqa: E402

# A workstream whose monthly gain is worth less than this against revenue does
# not make the plan: it is noise, and it would take a real subject's place.
# Measured on one month's step, which is about a third of what the old 90-day
# gap was worth, hence 1% rather than the 2% that filtered that gap.
GAIN_THRESHOLD = 0.01

# Window used as the internal reference. Six months: long enough to find a good
# level, short enough not to reach back to a period when the store worked
# differently.
WINDOW = 6

# Ceiling on ambition over one month when the reference level is old: a tenth
# better than today.
CAP = 0.10

# Monthly step on a dependency share, in points.
STEP = 0.02


def _best(series, key, direction="min", ignore_zero=True, within=WINDOW):
    """
    Best level reached over the reference window, current month excluded.
    Returns (value, months_ago) or (None, None).

    `ignore_zero` drops months at exactly zero: on a return rate, a perfect
    zero almost always means no returns were being recorded at the time, not
    that the store was flawless. Keeping it as a target would produce an
    absurd goal.
    """
    window = series[-(within + 1):-1]
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
    Returns (target, origin), origin being "best" when the best month is taken
    as is and "capped" when the ceiling binds, or (None, None).

    Sets the goal between what the store has already done and what can
    reasonably be aimed at in one month.

    A level reached one or two months ago is taken as is: the proof it can be
    done is fresh. An older level is capped at `cap` relative improvement,
    otherwise a metric degrading for six months would produce a target nobody
    can hold. This came up in real conditions: a return rate that went from
    0.8% to 17% in eight months produced a 6.7% target, inherited from a month
    when returns were not yet all recorded.
    """
    if best is None:
        return None, None
    if months_ago is not None and months_ago <= 2:
        return best, "best"
    bound = current * (1 - cap) if direction == "min" else current * (1 + cap)
    # The ceiling only counts as the reference when it actually binds: an old
    # best month within reach is still the best month.
    if (best < bound) if direction == "min" else (best > bound):
        return bound, "capped"
    return best, "best"


def _goal(series, key, current, direction="min"):
    """
    The internal reference: the best month of the window through `_target`,
    unless a month of the last two beats it. Then that recent month is the
    target, since the proof it can be done is fresh. Without this, an old best
    month would get capped below a level the store reached last month.
    """
    best, months_ago = _best(series, key, direction)
    target, origin = _target(current, best, months_ago, direction)
    recent, _ = _best(series, key, direction, within=2)
    if recent is not None and target is not None and \
            ((recent < target) if direction == "min" else (recent > target)):
        target, origin = recent, "best"
    return target, origin, best


REFERENCES = {"best": "priorities.ref_best_six",
              "capped": "priorities.ref_capped",
              "declared": "priorities.ref_declared",
              "declared_capped": "priorities.ref_declared_capped",
              "convention": "priorities.ref_convention"}


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
    target, origin, _ = _goal(series, "rate", rate, "min")

    # A threshold the merchant declared beats the internal reference: they know
    # what they tolerate on their product. A store already within it has no
    # refunds workstream. Beyond reach, the target stays capped at what one
    # month allows.
    ctx = data.get("context") or {}
    declared = ctx.get("acceptable_return_rate")
    if declared is None:
        declared = ctx.get("taux_retour_acceptable")
    if declared is not None:
        if rate <= declared:
            return
        floor = rate * (1 - CAP)
        # A history that already reached the threshold makes it reachable,
        # and the store is never pushed below what it declared tolerable.
        if declared >= floor or (target is not None and target <= declared):
            target, origin = declared, "declared"
        elif target is None or floor < target:
            target, origin = floor, "declared_capped"

    if target is None:
        target, origin = rate * (1 - CAP), "convention"
    if target >= rate:
        return

    gain = (rate - target) * gross
    out.append({
        "key": "returns", "nature": "leak",
        "title": L.t("priorities.titles.returns"),
        "finding": L.t("priorities.returns_finding",
                       amount=L.money(rt.get("amount") or 0, cur, True),
                       rate=L.pct(rate),
                       annual=L.money(abs(rt.get("amount") or 0) * 12, cur, True)),
        "goal": L.t("priorities.returns_goal", target=L.pct(target)),
        "reference": L.t(REFERENCES[origin]),
        "weight": gain * 12, "gain": gain, "unit": "rate",
        "current": rate, "target": target})


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
    target, origin, best = _goal(series, "cr", cr, "max")
    if target is None or target <= cr:
        return
    gain = (target - cr) * sessions * aov
    out.append({
        "key": "conversion", "nature": "leak",
        "title": L.t("priorities.titles.conversion"),
        "finding": L.t("priorities.conversion_finding", rate=L.pct(cr, 2),
                       best=L.pct(best, 2)),
        "goal": L.t("priorities.conversion_goal", target=L.pct(target, 2)),
        "reference": L.t(REFERENCES[origin]),
        "weight": gain * 12, "gain": gain, "unit": "rate2",
        "current": cr, "target": target,
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
        "current": rate, "target": ref})


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
        "current": value, "target": ref})


def _w_source_dependency(data, L, cur, out):
    # Orders with no identified referrer are left out: an absence of
    # attribution is not a source, and no workstream can reduce it.
    share, name = source_share(data)
    if share is None or share < 0.55 or share >= 1:
        return
    src = [s for s in (data.get("traffic_sources") or []) if s.get("label") == name]
    head = (src[0].get("sales") or 0) if src else 0
    target = share - STEP
    current_rest = head * (1 - share) / share
    goal_rest = head * (1 - target) / target
    gain = goal_rest - current_rest
    if gain <= 0:
        return
    out.append({
        "key": "source_dependency", "nature": "risk",
        "title": L.t("priorities.titles.source_dependency"),
        "finding": L.t("priorities.source_finding", share=L.pct(share),
                       name=name),
        "subject": name,
        "goal": L.t("priorities.source_goal", target=L.pct(target)),
        "reference": L.t("priorities.ref_step"),
        "weight": gain * 12, "gain": gain, "unit": "rate",
        "current": share, "target": target,
        "note": L.t("priorities.source_note",
                    current=L.money(current_rest, cur, True),
                    goal=L.money(goal_rest, cur, True))})


def _w_catalogue_concentration(data, L, cur, out):
    share = top3_share(data)
    if share is None or share < 0.60:
        return
    gross = data["sales_detail"]["gross_sales"]
    top3 = share * gross
    target = share - STEP
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


def compute(data, limit=3, lang=None, errors=None):
    """
    Return the retained workstreams, heaviest first.

    A workstream that trips on unexpected data is skipped so the report still
    ships, but never silently: the error is appended to `errors` when a list is
    given, and the builder prints it.
    """
    meta = data.get("meta") or {}
    L = lang if isinstance(lang, Lang) else Lang(lang or meta.get("lang", "fr"))
    cur = meta.get("currency", "EUR")
    revenue = (_kpis(data).get("total_sales") or {}).get("value") or 0

    out = []
    for w in WORKSTREAMS:
        try:
            w(data, L, cur, out)
        except Exception as exc:
            if errors is not None:
                errors.append(f"priorities.{w.__name__}: {exc!r}")

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
        c["current_txt"] = _fmt(L, c["current"], c["unit"], cur)
        c["target_txt"] = _fmt(L, c["target"], c["unit"], cur)
        c["gain_label"] = L.t("labels.gain_develop" if c["nature"] == "risk"
                              else "labels.gain_monthly")
    return plan


def to_state(priorities, meta):
    """
    Condensed form of the plan, stored in the shop metafield so next month's
    report can measure each target. Keys are language-independent.
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
            "monthly_gain": c["gain"],
            **({"subject": c["subject"]} if c.get("subject") else {}),
        } for c in priorities],
    }


def _measure(key, data, subject=None):
    """This month's value for a workstream key, or None if it cannot be read."""
    k = _kpis(data)
    if key == "returns":
        return (data.get("returns") or {}).get("rate")
    if key == "conversion":
        return (k.get("cr") or {}).get("value")
    if key == "margin":
        return (data.get("margin") or {}).get("margin_rate")
    if key == "basket":
        return (k.get("aov") or {}).get("value")
    if key == "source_dependency":
        # The share of the source the plan named, not of whichever source
        # leads this month.
        return source_share(data, subject)[0]
    if key == "catalogue_concentration":
        return top3_share(data)
    return None


MEASURABLE = ["returns", "conversion", "margin", "basket", "source_dependency",
              "catalogue_concentration"]


def follow_up(previous, data, lang=None):
    """
    Compares the targets last month's plan set for this month to what is
    measured. Returns one line per workstream, never qualifying the outcome.
    A workstream that
    cannot be measured this month keeps its line, with `met` set to None,
    rather than disappearing from the follow-up.
    """
    if not previous:
        return []
    items = previous.get("workstreams") or previous.get("chantiers") or []
    if not items:
        return []
    meta = data.get("meta") or {}
    L = lang if isinstance(lang, Lang) else Lang(lang or meta.get("lang", "fr"))
    cur = meta.get("currency", "EUR")
    # Plans written before workstreams carried a stable key fall back on the
    # translated title, which only matches within one language.
    by_title = {L.t(f"priorities.titles.{key}"): key for key in MEASURABLE}

    lines = []
    for c in items:
        key = c.get("key") or by_title.get(c.get("title") or c.get("titre"))
        unit = c.get("unit") or c.get("unite") or "rate"
        start = c.get("current", c.get("actuel"))
        # Plans written while the plan ran over 90 days carry milestones: the
        # first one is what was due this month.
        milestones = c.get("milestones") or c.get("jalons") or []
        due = milestones[0] if milestones else c.get("target", c.get("cible"))
        if due is None:
            continue
        value = _measure(key, data, c.get("subject"))
        going_down = due < (start if start is not None else due)
        met = None
        if value is not None:
            met = value <= due if going_down else value >= due
        # Titled in this report's language when the key is known, so a plan
        # stored in one language reads right in a report written in another.
        title = L.t(f"priorities.titles.{key}") if key in MEASURABLE \
            else c.get("title") or c.get("titre") or key
        lines.append({
            "title": title,
            "start": _fmt(L, start, unit, cur) if start is not None
            else L.t("common.na"),
            "target": _fmt(L, due, unit, cur),
            "measured": _fmt(L, value, unit, cur) if value is not None
            else L.t("common.na"),
            "met": met})
    return lines


if __name__ == "__main__":
    import json
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    code = sys.argv[2] if len(sys.argv) > 2 else None
    errors = []
    for c in compute(d, lang=code, errors=errors):
        print(f"--- {c['rank']}. {c['title']}")
        print(f"    {c['finding']}")
        print(f"    weight: {c['weight_txt']} | gain: {c['gain_txt']}")
        print(f"    goal: {c['goal']} ({c['reference']})")
        print(f"    from {c['current_txt']} to {c['target_txt']}")
        if c.get("note"):
            print(f"    note: {c['note']}")
    for e in errors:
        print(f"warning: {e}", file=sys.stderr)
