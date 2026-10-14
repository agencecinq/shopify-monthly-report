"""
Permanent metrics: recipes, the postcode to department mapping, and what each
view shows. The last test builds the deck and needs python-pptx.

    python3 -m pytest tests
"""

import copy
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "trente", "scripts"))

import custom_metrics as cm  # noqa: E402


@pytest.fixture
def data():
    with open(os.path.join(ROOT, "examples", "report.example.json"),
              encoding="utf-8") as f:
        return json.load(f)


def metric(data, mid):
    return copy.deepcopy(next(m for m in data["custom_metrics"] if m["id"] == mid))


# ---------------------------------------------------------------------------
# the bundled map
# ---------------------------------------------------------------------------

def test_map_covers_every_department():
    fr = cm.france()
    assert len(fr["names"]) == 101
    assert set(fr["frames"]["metro"]["shapes"]) | set(fr["frames"]["idf"]["shapes"]) \
        | {c for c in cm.OVERSEAS_COUNTRIES.values()} == set(fr["names"])
    for code in cm.OVERSEAS_COUNTRIES.values():
        assert code in fr["frames"][code]["shapes"]


def test_population_is_insee_and_mayotte_is_marked_missing():
    fr = cm.france()
    assert fr["sources"]["population_year"] == "2023"
    assert set(fr["names"]) - set(fr["population"]) == {"976"}
    assert 2_000_000 < fr["population"]["75"] < 2_300_000


def test_asset_fits_the_directory_limit():
    # The plugin directory holds any text file over 256 KiB for a reviewer.
    assert os.path.getsize(cm.ASSET) < 256 * 1024


# ---------------------------------------------------------------------------
# postcodes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("postal,country,dep", [
    ("75011", "FR", "75"),
    ("01000", "FR", "01"),
    (" 69 003", "FR", "69"),
    ("20000", "FR", "2A"),
    ("20167", "FR", "2A"),
    ("20200", "FR", "2B"),
    ("20600", "FR", "2B"),
    ("97110", "GP", "971"),
    ("97200", "FR", "972"),
    ("97400", "RE", "974"),
    ("97600", "YT", "976"),
    (None, "MQ", "972"),
])
def test_department_of_a_postcode(postal, country, dep):
    assert cm.department(postal, country) == dep


@pytest.mark.parametrize("postal,country", [
    ("98000", "FR"),      # Monaco
    ("97133", "FR"),      # Saint-Barthélemy
    ("97150", "GP"),      # Saint-Martin
    ("97500", "FR"),      # Saint-Pierre-et-Miquelon
    ("75011", "BE"),      # not France
    ("7501", "FR"),       # malformed
    ("", "FR"),
])
def test_postcodes_outside_the_map(postal, country):
    assert cm.department(postal, country) is None


# ---------------------------------------------------------------------------
# recipes
# ---------------------------------------------------------------------------

def test_example_recipes_are_valid(data):
    assert cm.validate_all(data["custom_metrics"]) == []


def test_flow_query_must_read_the_period(data):
    m = metric(data, "discount-code-share")
    m["queries"][0]["query"] = "FROM sales SHOW orders DURING last_month"
    assert any("START and END" in e for e in cm.validate(m))


def test_view_must_read_a_defined_query(data):
    m = metric(data, "discount-codes")
    m["rows"]["query"] = "elsewhere"
    assert any("does not define" in e for e in cm.validate(m))


def test_duplicate_ids_and_too_many_metrics(data):
    recipes = [metric(data, "subscribers")] * 2
    assert any("twice" in e for e in cm.validate_all(recipes))
    many = [dict(metric(data, "subscribers"), id=f"m{i}") for i in range(cm.MAX_METRICS + 1)]
    assert any("at most" in e for e in cm.validate_all(many))


def test_check_cli_reads_a_context(tmp_path, data, capsys):
    ctx = tmp_path / "context.json"
    ctx.write_text(json.dumps({"custom_metrics": data["custom_metrics"]}))
    sys.argv = ["custom_metrics.py", "--check", str(ctx)]
    with pytest.raises(SystemExit) as exc:
        cm.main()
    assert exc.value.code == 0
    assert json.loads(capsys.readouterr().out)["errors"] == []


# ---------------------------------------------------------------------------
# views
# ---------------------------------------------------------------------------

def test_map_counts_every_order_once(data):
    m = cm.prepare(metric(data, "orders-by-department"))
    france = next(c for c in data["sales_by_country"] if c["label"] == "France")
    assert m["mapped"] + m["outside"] == france["orders"]
    assert m["departments"]["75"]["value"] == 4
    assert m["departments"]["2A"]["value"] == 1


def test_map_rate_is_per_100000_inhabitants(data):
    m = cm.prepare(metric(data, "orders-by-department"))
    paris = m["departments"]["75"]
    assert paris["rate"] == pytest.approx(4 / cm.france()["population"]["75"] * 100000)
    # Mayotte has no INSEE reference population: no rate, no class.
    assert m["departments"]["976"]["rate"] is None
    assert m["departments"]["976"]["class"] is None
    assert m["no_population"] == ["976"]


def test_map_top_ten_is_ranked_by_rate(data):
    m = cm.prepare(metric(data, "orders-by-department"))
    rates = [t["rate"] for t in m["top"]]
    assert rates == sorted(rates, reverse=True) and len(rates) == 10
    assert m["top"][0]["code"] == "2A"


def test_map_counts_orders_outside_france_apart(data):
    m = metric(data, "orders-by-department")
    m["data"]["orders"].append({"shipping_country_code": "FR",
                                "shipping_postal_code": "98000", "orders": 2})
    assert cm.prepare(m)["outside"] == 2


def test_map_classes_put_every_department_in_a_shade():
    bounds = cm.classes([0, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    assert bounds == [2, 4, 6, 8, 10]
    assert cm.class_of(0, bounds) == 0
    assert cm.class_of(1, bounds) == 1
    assert cm.class_of(10, bounds) == 5
    assert cm.class_of(None, bounds) is None


def test_stock_kpi_compares_with_the_last_report(data):
    m = cm.prepare(metric(data, "subscribers"))
    assert m["value"] == 131 and m["compare"] == 118
    assert m["basis"] == ("last_report", "July 2026")
    assert [d["label"] for d in m["details"]] == ["Their orders this month",
                                                  "Their sales this month"]


def test_stock_kpi_without_a_last_value_has_no_change(data):
    raw = metric(data, "subscribers")
    del raw["last"]
    m = cm.prepare(raw)
    assert m["compare"] is None and m["delta"] is None


def test_lower_bound_count_is_flagged(data):
    raw = metric(data, "subscribers")
    raw["data"]["count"] = [{"count": 10000, "precision": "AT_LEAST"}]
    assert cm.prepare(raw)["at_least"] is True


def test_ratio_kpi_is_a_share(data):
    m = cm.prepare(metric(data, "discount-code-share"))
    assert m["unit"] == "percent"
    assert m["value"] == pytest.approx(47 / 260)
    assert m["compare"] == pytest.approx(39 / 291)


def test_bars_are_sorted_and_cut(data):
    raw = metric(data, "discount-codes")
    raw["rows"]["limit"] = 2
    m = cm.prepare(raw)
    assert [r["label"] for r in m["rows"]] == ["WELCOME10", "SUMMER15"]


def test_rows_without_label_are_dropped(data):
    raw = metric(data, "discount-codes")
    raw["data"]["codes"].append({"discount_code": None, "orders": 99})
    assert all(r["label"] != "None" for r in cm.prepare(raw)["rows"])


def test_missing_rows_leave_the_metric_out(data):
    raw = metric(data, "collection-travel")
    del raw["data"]["travel"]
    with pytest.raises(cm.MetricError):
        cm.prepare(raw)


def test_last_values_cover_stock_metrics_only(data):
    models = [cm.prepare(m) for m in data["custom_metrics"]]
    assert cm.last_values(models, "2026-08", "August 2026") == {
        "subscribers": {"period": "2026-08", "label": "August 2026", "value": 131}}


# ---------------------------------------------------------------------------
# the deck
# ---------------------------------------------------------------------------

def test_deck_has_one_slide_per_metric(data, tmp_path):
    pytest.importorskip("pptx")
    import build_report
    from i18n import Lang
    from brand import build_palette
    build_report.set_lang(Lang("fr"))
    out, chapters, _, _, warnings, last = build_report.build(
        data, build_palette("", {}), logo=None, out=str(tmp_path / "r.pptx"))
    assert warnings == []
    assert chapters[-1] == Lang("fr").t("chapters.custom")
    assert last["subscribers"]["value"] == 131
    from pptx import Presentation
    titles = [next((sh.text_frame.text for sh in s.shapes if sh.has_text_frame
                    and sh.text_frame.text.strip()), "")
              for s in Presentation(out).slides]
    for m in data["custom_metrics"]:
        assert m["title"] in titles


def test_broken_metric_is_a_warning_not_a_crash(data, tmp_path):
    pytest.importorskip("pptx")
    import build_report
    from i18n import Lang
    from brand import build_palette
    build_report.set_lang(Lang("en"))
    del data["custom_metrics"][0]["data"]
    _, _, _, _, warnings, _ = build_report.build(
        data, build_palette("", {}), logo=None, out=str(tmp_path / "r.pptx"))
    assert any("orders-by-department" in w for w in warnings)
