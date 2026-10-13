"""
Regression tests for the salience and priority engines.

They run on the worked example, then on small variations of it, and check the
figures and wording a reader would see. No Shopify access, no python-pptx.

    python3 -m pytest tests
"""

import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "shopify-monthly-report", "scripts"))

import highlights  # noqa: E402
import priorities  # noqa: E402
import shared  # noqa: E402
from i18n import Lang  # noqa: E402

EN = Lang("en")


@pytest.fixture
def data():
    with open(os.path.join(ROOT, "examples", "report.example.json"),
              encoding="utf-8") as f:
        return json.load(f)


def plan(data, **kw):
    errors = []
    out = priorities.compute(data, lang=EN, errors=errors, **kw)
    assert errors == []
    return {c["key"]: c for c in out}


# ---------------------------------------------------------------------------
# targets and the reference they display
# ---------------------------------------------------------------------------

def test_target_recent_best_is_taken_as_is():
    assert priorities._target(0.0145, 0.0172, 1, "max") == (0.0172, "best")


def test_target_old_best_within_reach_is_not_labelled_capped():
    # 1.55% is under the 1.595% one-month ceiling: the best month is the
    # target, and the slide must say so.
    target, origin = priorities._target(0.0145, 0.0155, 6, "max")
    assert target == 0.0155 and origin == "best"


def test_target_old_best_out_of_reach_is_capped():
    target, origin = priorities._target(0.0145, 0.0250, 6, "max")
    assert target == pytest.approx(0.0145 * 1.1) and origin == "capped"


def test_target_capped_downwards():
    target, origin = priorities._target(0.17, 0.067, 8, "min")
    assert target == pytest.approx(0.17 * 0.9) and origin == "capped"


def _flatten_recent_conversion(data, rate=0.0140):
    for row in data["history"]["conversion"][-3:-1]:
        row["conversion_rate"] = rate


def test_conversion_reference_matches_target(data):
    # The best month of the window is six months old and out of reach.
    _flatten_recent_conversion(data)
    c = plan(data)["conversion"]
    assert c["target"] == pytest.approx(0.0145 * 1.1)
    assert c["reference"] == EN.t("priorities.ref_capped")
    # The finding quotes the best month, not the target.
    assert "1.62%" in c["finding"]


def test_conversion_old_best_within_reach_is_the_target(data):
    _flatten_recent_conversion(data)
    for row in data["history"]["conversion"][-7:-3]:
        row["conversion_rate"] = 0.0150
    data["history"]["conversion"][-7]["conversion_rate"] = 0.0155
    c = plan(data)["conversion"]
    assert c["target_txt"] == "1.55%"
    assert c["reference"] == EN.t("priorities.ref_best_six")


def test_recent_month_beats_capped_old_best(data):
    # The best month is old and gets capped at 1.595%, but last month did
    # 1.72%: that fresh level is the target.
    data["history"]["conversion"][-7]["conversion_rate"] = 0.0300
    c = plan(data)["conversion"]
    assert c["target"] == 0.0172
    assert c["reference"] == EN.t("priorities.ref_best_six")
    assert "3.00%" in c["finding"]


# ---------------------------------------------------------------------------
# refunds and the merchant's declared threshold
# ---------------------------------------------------------------------------

def test_returns_declared_threshold_is_the_target(data):
    # 8% is beyond a one-month step from 10%, but last month did 7.8%: the
    # threshold is reachable, and the target never goes below it.
    c = plan(data)["returns"]
    assert c["target"] == 0.08
    assert c["reference"] == EN.t("priorities.ref_declared")


def test_returns_within_declared_threshold_has_no_workstream(data):
    data["context"]["acceptable_return_rate"] = 0.15
    assert "returns" not in plan(data)


def test_returns_at_declared_threshold_has_no_workstream(data):
    data["context"]["acceptable_return_rate"] = 0.10
    assert "returns" not in plan(data)


def test_returns_declared_out_of_reach_is_capped(data):
    data["context"]["acceptable_return_rate"] = 0.02
    data["history"]["returns"] = []
    c = plan(data)["returns"]
    assert c["target"] == pytest.approx(0.09)
    assert c["reference"] == EN.t("priorities.ref_declared_capped")


def test_returns_convention_without_history_or_threshold(data):
    del data["context"]["acceptable_return_rate"]
    data["history"]["returns"] = []
    c = plan(data)["returns"]
    assert c["target"] == pytest.approx(0.09)
    assert c["reference"] == EN.t("priorities.ref_convention")


def test_returns_legacy_french_key_still_read(data):
    del data["context"]["acceptable_return_rate"]
    data["context"]["taux_retour_acceptable"] = 0.15
    assert "returns" not in plan(data)


# ---------------------------------------------------------------------------
# unattributed traffic is never a source
# ---------------------------------------------------------------------------

def test_unattributed_row_is_never_the_dependency(data):
    out = {c["key"]: c for c in priorities.compute(data, lang=EN, limit=10)}
    c = out["source_dependency"]
    assert c["subject"] == "Search"
    assert "Direct" not in c["finding"]
    # 11,400 of 17,900 attributed.
    assert c["current"] == pytest.approx(11400 / 17900)


@pytest.mark.parametrize("row", [
    {"label": "Direct or unidentified"},
    {"label": "Direct ou non identifié"},
    {"label": "Unidentified"},
    {"label": "Anything", "source": ""},
    {"label": "Anything", "source": "unknown"},
    {"label": "Anything", "unattributed": True},
])
def test_unattributed_detection(row):
    assert shared.is_unattributed(row)


@pytest.mark.parametrize("row", [
    {"label": "Search"},
    {"label": "Direct mail", "unattributed": False},
    {"label": "Anything", "source": "search"},
])
def test_attributed_detection(row):
    assert not shared.is_unattributed(row)


def test_highlight_never_names_unattributed(data):
    texts = [h["text"] for h in highlights.compute(data, lang=EN)]
    assert not any("Direct" in t for t in texts)


def test_only_unattributed_revenue_gives_no_dependency(data):
    data["traffic_sources"] = [
        {"label": "Direct or unidentified", "sales": 30000, "unattributed": True}]
    assert "source_dependency" not in plan(data)


# ---------------------------------------------------------------------------
# follow-up
# ---------------------------------------------------------------------------

def test_follow_up_measures_risk_workstreams(data):
    lines = {l["title"]: l for l in
             priorities.follow_up(data["previous_plan"], data, lang=EN)}
    assert set(lines) == {"Average order value", "Catalogue concentration",
                          "Dependence on one source"}
    assert lines["Dependence on one source"]["measured"] == "63.7%"
    assert lines["Dependence on one source"]["met"] is True
    assert lines["Catalogue concentration"]["met"] is True
    assert lines["Average order value"]["met"] is False


def test_follow_up_reads_legacy_90_day_plans(data):
    # A plan stored before the switch carries milestones: the first one is
    # what was due this month.
    legacy = {"workstreams": [{"key": "returns", "title": "Refunds",
                               "unit": "rate", "current": 0.12, "target": 0.084,
                               "milestones": [0.108, 0.096, 0.084]}]}
    line = priorities.follow_up(legacy, data, lang=EN)[0]
    assert line["target"] == "10.8%" and line["met"] is True


def test_follow_up_measures_the_target(data):
    prev = {"workstreams": [{"key": "returns", "unit": "rate",
                             "current": 0.12, "target": 0.095}]}
    line = priorities.follow_up(prev, data, lang=EN)[0]
    assert line["target"] == "9.5%" and line["met"] is False


def test_follow_up_keeps_unmeasurable_line(data):
    data["traffic_sources"] = [s for s in data["traffic_sources"]
                               if s["label"] != "Search"]
    lines = {l["title"]: l for l in
             priorities.follow_up(data["previous_plan"], data, lang=EN)}
    line = lines["Dependence on one source"]
    assert line["met"] is None and line["measured"] == EN.t("common.na")


def test_follow_up_titles_follow_report_language(data):
    lines = priorities.follow_up(data["previous_plan"], data, lang=Lang("fr"))
    assert lines[0]["title"] == Lang("fr").t("priorities.titles.basket")


def test_state_round_trips_into_follow_up(data):
    state = priorities.to_state(priorities.compute(data, lang=EN), data["meta"])
    lines = priorities.follow_up(state, data, lang=EN)
    assert len(lines) == len(state["workstreams"])


# ---------------------------------------------------------------------------
# errors are reported, not swallowed
# ---------------------------------------------------------------------------

def test_rule_errors_are_reported(data):
    data["returns"] = "not an object"
    errors = []
    highlights.compute(data, lang=EN, errors=errors)
    priorities.compute(data, lang=EN, errors=errors)
    assert "highlights._r_returns" in " ".join(errors)
    assert "priorities._w_returns" in " ".join(errors)


# ---------------------------------------------------------------------------
# series end on the period under review
# ---------------------------------------------------------------------------

def test_align_drops_partial_month(data):
    data["seasonality"].append({"label": "Sep 26", "month": "2026-09",
                                "value": 9000.0})
    warnings = shared.align_to_period(data)
    assert data["seasonality"][-1]["month"] == "2026-08"
    assert any("dropped" in w for w in warnings)


def test_align_flags_series_ending_early(data):
    data["history"]["returns"].pop()
    warnings = shared.align_to_period(data)
    assert any("ends on 2026-07" in w for w in warnings)


def test_align_flags_rows_without_month(data):
    for row in data["seasonality"]:
        del row["month"]
    warnings = shared.align_to_period(data)
    assert any("seasonality" in w and "month" in w for w in warnings)


def test_example_is_aligned(data):
    assert shared.align_to_period(copy.deepcopy(data)) == []


# ---------------------------------------------------------------------------
# the worked example stays coherent
# ---------------------------------------------------------------------------

def test_example_history_matches_kpis(data):
    k = {x["key"]: x for x in data["kpis"]}
    conv = data["history"]["conversion"]
    assert conv[-1]["conversion_rate"] == k["cr"]["value"]
    assert conv[-2]["conversion_rate"] == k["cr"]["compare"]["previous_period"]
    assert conv[-1]["sessions"] == data["funnel"]["sessions"]
    ret = data["history"]["returns"][-1]
    assert ret["gross_sales"] == data["sales_detail"]["gross_sales"]
    assert ret["reversals"] == data["sales_detail"]["sales_reversals"]


def test_example_plan(data):
    out = priorities.compute(data, lang=EN)
    assert [c["key"] for c in out] == ["conversion", "returns", "margin"]
    # One target per workstream, for next month: no milestones any more.
    assert all("milestones" not in c for c in out)


def _flat(d, prefix=""):
    out = set()
    for k, v in d.items():
        if k.startswith("_"):
            continue
        out |= _flat(v, f"{prefix}{k}.") if isinstance(v, dict) else {prefix + k}
    return out


def test_catalogues_share_keys():
    i18n = os.path.join(ROOT, "skills", "shopify-monthly-report", "i18n")
    keys = {}
    for name in os.listdir(i18n):
        if name.endswith(".json"):
            with open(os.path.join(i18n, name), encoding="utf-8") as f:
                keys[name] = _flat(json.load(f))
    reference = keys.pop("en.json")
    for name, other in keys.items():
        assert other == reference, (name, sorted(other ^ reference))
