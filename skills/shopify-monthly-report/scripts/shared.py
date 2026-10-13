"""
Helpers shared by the salience engine and the priority engine.

Both read the same report.json and must agree on two things: which traffic
source counts as attributed, and where the monthly series end.
"""

# Fallback for reports written before rows carried `unattributed`. The label
# is translated, so this only catches the wordings the collection guide gives.
_UNATTRIBUTED_WORDS = ("direct", "unidentified", "unknown", "non identifi",
                       "inconnu")


def is_unattributed(row):
    """
    True for the traffic source row that holds orders with no identified
    referrer. It is not a source: it is the absence of one, so it can neither
    be a dependency nor be reduced.
    """
    if row.get("unattributed") is not None:
        return bool(row["unattributed"])
    if "source" in row:
        return (row.get("source") or "").strip().lower() in ("", "unknown")
    label = (row.get("label") or "").lower()
    return any(w in label for w in _UNATTRIBUTED_WORDS)


def attributed_sources(data):
    """Traffic sources with an identified referrer, largest first."""
    src = [s for s in (data.get("traffic_sources") or []) if not is_unattributed(s)]
    return sorted(src, key=lambda s: -(s.get("sales") or 0))


def source_share(data, label=None):
    """
    Share of attributed revenue held by `label`, or by the largest attributed
    source when no label is given. Returns (share, label) or (None, None).
    """
    src = attributed_sources(data)
    total = sum(s.get("sales") or 0 for s in src)
    if not src or total <= 0:
        return None, None
    row = next((s for s in src if s.get("label") == label), None) if label \
        else src[0]
    if row is None:
        return None, None
    return (row.get("sales") or 0) / total, row.get("label")


def top3_share(data):
    """Share of gross sales made by the three best-selling products."""
    tp = data.get("top_products") or []
    gross = (data.get("sales_detail") or {}).get("gross_sales")
    if len(tp) < 3 or not gross:
        return None
    return sum(p.get("sales") or 0 for p in tp[:3]) / gross


# Monthly series whose last row must be the month under review.
SERIES = [("seasonality",), ("history", "returns"), ("history", "conversion")]


def _get(data, path):
    node = data
    for key in path:
        node = (node or {}).get(key)
    return node


def _set(data, path, value):
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value


def align_to_period(data):
    """
    Makes every monthly series end on the month under review, and returns the
    warnings raised doing so.

    A history queried `UNTIL today` on 12 October for a September report ends
    on a partial October. Left as is, the seasonality rank compares a twelve-day
    month with full ones, and the plan's reference window slides by one month.
    Rows carry `month` as `YYYY-MM`; rows after the period are dropped.
    """
    period = ((data.get("meta") or {}).get("period_start") or "")[:7]
    warnings = []
    if not period:
        return warnings
    for path in SERIES:
        rows = _get(data, path)
        if not rows:
            continue
        name = ".".join(path)
        if not all(r.get("month") for r in rows):
            warnings.append(f"{name}: rows carry no `month`, so the last row "
                            f"cannot be checked against {period}")
            continue
        kept = [r for r in rows if r["month"] <= period]
        if len(kept) < len(rows):
            dropped = ", ".join(r["month"] for r in rows if r["month"] > period)
            warnings.append(f"{name}: dropped months after {period} ({dropped})")
            _set(data, path, kept)
        if kept and kept[-1]["month"] != period:
            warnings.append(f"{name}: ends on {kept[-1]['month']}, not on "
                            f"the period under review ({period})")
    return warnings
