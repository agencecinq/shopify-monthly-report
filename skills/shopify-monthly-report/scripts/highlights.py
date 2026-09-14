"""
Salience engine.

Produces the findings on the "what stands out" slide from data already
collected. Rules are deterministic and numeric: the same report.json always
yields the same findings, and no finding states a cause or a recommendation.

Each rule returns:
    {"text": sentence, "score": importance 0-100, "tag": short label}

The score only decides which findings make the cut when there are more than
there is room for. It is never displayed.

All wording comes from the language catalogue; nothing user-visible is written
in this file.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from i18n import Lang  # noqa: E402


def _rel(cur, ref):
    if cur is None or not ref:
        return None
    return (cur - ref) / abs(ref)


def _kpi(data, key):
    for k in data.get("kpis") or []:
        if k.get("key") == key:
            return k
    return None


def _vs(L, data, ref_key):
    labels = (data.get("meta", {}).get("comparison_labels") or {})
    return L.t("common.vs",
               label=labels.get(ref_key, L.t("common.reference_period")))


# ---------------------------------------------------------------------------
# rules
# ---------------------------------------------------------------------------

def _r_annual_objective(data, L, cur, out):
    ytd = data.get("ytd") or {}
    done, target = ytd.get("value"), ytd.get("objectif") or ytd.get("target")
    if not done or not target:
        return
    txt = L.t("highlights.annual_objective", value=L.money(done, cur, True),
              share=L.pct(done / target), target=L.money(target, cur, True))
    months = ytd.get("mois_ecoules") or ytd.get("months_elapsed")
    if months:
        txt += L.t("highlights.annual_objective_months", months=months)
    out.append({"tag": L.t("highlights.tags.objective"), "text": txt + ".",
                "score": 72})


def _r_product_concentration(data, L, cur, out):
    tp = data.get("top_products") or []
    if len(tp) < 3:
        return
    gross = (data.get("sales_detail") or {}).get("gross_sales") or \
        sum(p.get("sales") or 0 for p in tp)
    if gross <= 0:
        return
    share = sum(p.get("sales") or 0 for p in tp[:3]) / gross
    if share < 0.5:
        return
    out.append({
        "tag": L.t("highlights.tags.concentration"),
        "text": L.t("highlights.concentration_products", share=L.pct(share),
                    names=", ".join(p["label"] for p in tp[:3])),
        "score": 50 + share * 40})


def _r_source_concentration(data, L, cur, out):
    src = data.get("traffic_sources") or []
    if not src:
        return
    total = sum(s.get("sales") or 0 for s in src)
    if total <= 0:
        return
    share = (src[0].get("sales") or 0) / total
    if share < 0.55:
        return
    out.append({
        "tag": L.t("highlights.tags.acquisition"),
        "text": L.t("highlights.concentration_source", share=L.pct(share),
                    name=src[0]["label"]),
        "score": 40 + share * 35})


def _r_channels(data, L, cur, out):
    ch = data.get("channels") or []
    if len(ch) < 2:
        return
    total = sum(c.get("sales") or 0 for c in ch)
    if total <= 0:
        return

    def online(c):
        # The label is translated in the report, so the word "online" cannot be
        # relied on. The `online` key in report.json is authoritative.
        if c.get("online") is not None:
            return bool(c["online"])
        lab = (c.get("label") or "").lower()
        return "online store" in lab or "en ligne" in lab

    others = [c for c in ch if not online(c)]
    if not others or len(others) == len(ch):
        return
    share = sum(c.get("sales") or 0 for c in others) / total
    if share < 0.08:
        return
    out.append({
        "tag": L.t("highlights.tags.channels"),
        "text": L.t("highlights.offline_channels", share=L.pct(share),
                    names=", ".join(c["label"] for c in others[:3])),
        "score": 35 + share * 60})


def _r_returns(data, L, cur, out):
    rt = data.get("returns") or {}
    rate = rt.get("rate")
    if rate is None:
        return
    sd = data.get("sales_detail") or {}
    ref_rev = (sd.get("compare") or {}).get("sales_reversals")
    ref_gross = (sd.get("compare") or {}).get("gross_sales")
    gap = None
    if ref_rev and ref_gross:
        gap = rate - abs(ref_rev) / abs(ref_gross)
    if rate >= 0.10:
        txt = L.t("highlights.returns_high", rate=L.pct(rate))
        if gap is not None and abs(gap) >= 0.015:
            txt += L.t("highlights.returns_high_delta",
                       direction=L.t("highlights.direction_up" if gap > 0
                                     else "highlights.direction_down"),
                       points=L.points(gap))
        out.append({"tag": L.t("highlights.tags.returns"), "text": txt + ".",
                    "score": 45 + rate * 120})
    elif gap is not None and abs(gap) >= 0.04:
        out.append({
            "tag": L.t("highlights.tags.returns"),
            "text": L.t("highlights.returns_shift",
                        direction=L.t("highlights.returns_up" if gap > 0
                                      else "highlights.returns_down"),
                        points=L.points(gap), rate=L.pct(rate)),
            "score": 40 + abs(gap) * 200})


def _r_traffic_vs_revenue(data, L, cur, out):
    rev, conv = _kpi(data, "total_sales"), _kpi(data, "cr")
    if not rev or not conv:
        return
    ref_key = next(iter((rev.get("compare") or {})), None)
    if not ref_key:
        return
    vs = _vs(L, data, ref_key)
    d_rev = _rel(rev.get("value"), (rev.get("compare") or {}).get(ref_key))
    d_cv = _rel(conv.get("value"), (conv.get("compare") or {}).get(ref_key))
    sess = data.get("sessions_compare") or {}
    d_se = _rel(sess.get("value"), sess.get(ref_key))
    if d_rev is None:
        return
    if d_se is not None and d_rev * d_se < 0 and abs(d_rev) + abs(d_se) >= 0.10:
        out.append({
            "tag": L.t("highlights.tags.traffic"),
            "text": L.t("highlights.traffic_divergence",
                        traffic_dir=L.t("highlights.rises" if d_se > 0
                                        else "highlights.falls"),
                        traffic=L.pct(abs(d_se)),
                        revenue_dir=L.t("highlights.rises" if d_rev > 0
                                        else "highlights.falls"),
                        revenue=L.pct(abs(d_rev)), vs=vs),
            "score": 70 + (abs(d_rev) + abs(d_se)) * 40})
    if d_cv is not None and abs(d_cv) >= 0.15 and conv.get("value") is not None:
        out.append({
            "tag": L.t("highlights.tags.conversion"),
            "text": L.t("highlights.conversion_shift",
                        **{"from": L.pct((conv.get("compare") or {}).get(ref_key), 2),
                           "to": L.pct(conv["value"], 2), "vs": vs}),
            "score": 55 + abs(d_cv) * 45})


def _r_basket(data, L, cur, out):
    aov = _kpi(data, "aov")
    if not aov:
        return
    ref_key = next(iter((aov.get("compare") or {})), None)
    if not ref_key:
        return
    d = _rel(aov.get("value"), (aov.get("compare") or {}).get(ref_key))
    if d is None or abs(d) < 0.10:
        return
    out.append({
        "tag": L.t("highlights.tags.basket"),
        "text": L.t("highlights.basket_shift",
                    direction=L.t("highlights.basket_up" if d > 0
                                  else "highlights.basket_down"),
                    change=L.pct(abs(d)), value=L.money(aov["value"], cur),
                    vs=_vs(L, data, ref_key)),
        "score": 35 + abs(d) * 60})


def _r_margin(data, L, cur, out):
    mg = data.get("margin") or {}
    rate, ref = mg.get("margin_rate"), mg.get("compare_margin_rate")
    if rate is None or ref is None or abs(rate - ref) < 0.02:
        return
    out.append({
        "tag": L.t("highlights.tags.margin"),
        "text": L.t("highlights.margin_shift",
                    direction=L.t("highlights.margin_up" if rate > ref
                                  else "highlights.margin_down"),
                    points=L.points(rate - ref), rate=L.pct(rate)),
        "score": 40 + abs(rate - ref) * 150})


def _r_customers(data, L, cur, out):
    c = data.get("customers") or {}
    new, ret = c.get("new"), c.get("returning")
    if new is None or ret is None or (new + ret) == 0:
        return
    total = new + ret
    share = new / total
    if share >= 0.85:
        out.append({
            "tag": L.t("highlights.tags.customers"),
            "text": L.t("highlights.mostly_new", share=L.pct(share),
                        new=L.num(new), total=L.num(total)),
            "score": 30 + share * 20})
    elif share <= 0.55:
        out.append({
            "tag": L.t("highlights.tags.customers"),
            "text": L.t("highlights.mostly_returning", share=L.pct(1 - share),
                        returning=L.num(ret), total=L.num(total)),
            "score": 35 + (1 - share) * 30})


def _r_stock(data, L, cur, out):
    inv = data.get("inventory") or []
    stars = {p["label"] for p in (data.get("top_products") or [])[:5]}
    low = [i for i in inv[:6]
           if i.get("ending_units") is not None and i["ending_units"] <= 15
           and (i.get("sold") or 0) > 0]
    if not low:
        return
    i = ([x for x in low if x["label"] in stars] or low)[0]
    coverage = ""
    if i.get("sold"):
        days = round(i["ending_units"] / (i["sold"] / 30.0))
        if days < 60:
            coverage = L.t("highlights.stock_coverage", days=days)
    out.append({
        "tag": L.t("highlights.tags.stock"),
        "text": L.t("highlights.stock_low", name=i["label"],
                    units=L.num(i["ending_units"]), coverage=coverage),
        "score": 45 + max(0, 20 - i["ending_units"])})


def _r_seasonality(data, L, cur, out):
    hist = data.get("seasonality") or []
    if len(hist) < 12:
        return
    values = [h.get("value") or 0 for h in hist[-12:]]
    v = hist[-1].get("value") or 0
    if v not in values:
        return
    rank = sorted(values, reverse=True).index(v) + 1
    if rank == 1:
        out.append({"tag": L.t("highlights.tags.seasonality"),
                    "text": L.t("highlights.best_month"), "score": 65})
    elif rank >= len(values) - 1:
        out.append({"tag": L.t("highlights.tags.seasonality"),
                    "text": L.t("highlights.worst_month"), "score": 60})
    elif rank <= 3:
        out.append({"tag": L.t("highlights.tags.seasonality"),
                    "text": L.t("highlights.month_rank", rank=rank), "score": 35})


def _r_orders_vs_online(data, L, cur, out):
    online = (data.get("funnel") or {}).get("purchase")
    orders = _kpi(data, "orders")
    if not orders or online is None or not orders.get("value"):
        return
    total = orders["value"]
    if total <= 0 or online <= 0 or abs(total - online) / total < 0.20:
        return
    out.append({
        "tag": L.t("highlights.tags.scope"),
        "text": L.t("highlights.orders_vs_online", orders=L.num(total),
                    online=L.num(online)),
        "score": 30})


def _r_category(data, L, cur, out):
    cats = [c for c in (data.get("categories") or []) if c.get("label")]
    if len(cats) < 2:
        return
    total = sum(c.get("sales") or 0 for c in cats)
    if total <= 0:
        return
    share = (cats[0].get("sales") or 0) / total
    if share < 0.55:
        return
    out.append({
        "tag": L.t("highlights.tags.range"),
        "text": L.t("highlights.category_share", name=cats[0]["label"],
                    share=L.pct(share)),
        "score": 30 + share * 25})


RULES = [
    _r_annual_objective,
    _r_traffic_vs_revenue,
    _r_seasonality,
    _r_returns,
    _r_product_concentration,
    _r_margin,
    _r_stock,
    _r_channels,
    _r_source_concentration,
    _r_basket,
    _r_customers,
    _r_category,
    _r_orders_vs_online,
]


def compute(data, limit=6, lang=None):
    """Return the most salient findings, strongest first."""
    meta = data.get("meta") or {}
    L = lang if isinstance(lang, Lang) else Lang(lang or meta.get("lang", "fr"))
    cur = meta.get("currency", "EUR")

    out = []
    for rule in RULES:
        try:
            rule(data, L, cur, out)
        except Exception:
            # A rule that trips on unexpected data must never stop the report.
            continue
    out.sort(key=lambda h: -h["score"])

    seen, kept = set(), []
    for h in out:
        if h["tag"] in seen:
            continue
        seen.add(h["tag"])
        kept.append(h)
        if len(kept) == limit:
            break
    return kept


if __name__ == "__main__":
    import json
    d = json.load(open(sys.argv[1], encoding="utf-8"))
    code = sys.argv[2] if len(sys.argv) > 2 else None
    for h in compute(d, lang=code):
        print(f"[{h['tag']:<14}] {h['text']}")
