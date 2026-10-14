"""
Builds the report as a Claude Slides deck instead of a .pptx.

Prototype: cover, the month at a glance, daily revenue, and next month's plan.
Standard library only, so it runs in any sandbox, Claude Desktop included.

The script writes the deck's files under `--root`:

    project/deck.json           the index: title, slide order, typefaces
    project/slides/<id>.html    one <section> per slide, 1920x1080, inline styles

Claude then publishes that folder to the deck. Every figure and every sentence
on the slides comes from report.json and the engines, exactly as with the
.pptx: the model never lays out or rewrites a slide.

    python3 build_slides.py --data report.json --theme settings_data.json \\
        --lang en --root deck/
"""

import argparse
import datetime
import html
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import highlights as hl_mod  # noqa: E402
import priorities as pr_mod  # noqa: E402
import shared  # noqa: E402
from brand import build_palette, load_settings  # noqa: E402
from i18n import Lang  # noqa: E402

W, H = 1920, 1080
PAD = 128          # side and top margins
PAD_FOOT = 160     # bottom margin on slides with a footer row

# One type scale for the whole deck.
SIZE = {"display": 104, "title": 56, "value": 60, "lead": 34, "body": 28,
        "small": 24}


def fs(key):
    """A size from the type scale, as a CSS length."""
    return f"{SIZE[key]}px"


def esc(text):
    return html.escape(str(text), quote=True)


def style(**props):
    return ";".join(f"{k.replace('_', '-')}:{v}" for k, v in props.items()
                    if v is not None)


# ---------------------------------------------------------------------------
# typefaces
# ---------------------------------------------------------------------------

def _theme_family(handle):
    """'playfair_display_n7' -> 'Playfair Display'. Shopify's font handles are
    Google Fonts families for the free theme fonts."""
    if not isinstance(handle, str) or not handle:
        return None
    name = re.sub(r"_[in]\d+$", "", handle).replace("_", " ").strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 _-]{0,39}", name or ""):
        return None
    return " ".join(w.capitalize() for w in name.split())


def typefaces(theme_raw):
    """Heading and body families from the theme, with basic-face fallbacks."""
    current = load_settings(theme_raw) if theme_raw else {}
    current = current.get("current", current) if isinstance(current, dict) else {}
    if not isinstance(current, dict):
        current = {}
    heading = _theme_family(current.get("type_header_font")
                            or current.get("heading_font"))
    body = _theme_family(current.get("type_body_font") or current.get("text_font"))
    faces = {}
    for fam in {heading, body} - {None}:
        faces[fam.lower().replace(" ", "-")] = {
            "family": fam,
            "href": "https://fonts.googleapis.com/css2?family="
                    + fam.replace(" ", "+") + ":wght@400..800&display=swap"}
    stack = lambda fam, basic, generic: (  # noqa: E731
        f"'{fam}', {basic}, {generic}" if fam else f"{basic}, {generic}")
    return (stack(heading, "Georgia", "serif") if heading
            else stack(None, "Arial", "sans-serif"),
            stack(body, "Arial", "sans-serif"), faces)


# ---------------------------------------------------------------------------
# formatting, same rules as the .pptx builder
# ---------------------------------------------------------------------------

class Fmt:
    def __init__(self, lang, currency):
        self.L, self.cur = lang, currency

    def value(self, v, kind):
        if v is None:
            return self.L.t("common.na")
        if kind == "money":
            return self.L.money(v, self.cur, short=True)
        if kind == "percent":
            return self.L.pct(v, 2 if abs(v) < 0.1 else 1)
        return self.L.num(v)

    def delta(self, cur_v, ref_v):
        if cur_v is None or not ref_v:
            return None, 0
        d = (cur_v - ref_v) / abs(ref_v)
        sign = "+" if d >= 0 else ""
        return (f"{sign}{self.L.num(d * 100, 1)}{self.L.percent_space}%",
                1 if d > 0 else (-1 if d < 0 else 0))


# ---------------------------------------------------------------------------
# slide chrome
# ---------------------------------------------------------------------------

class Deck:
    def __init__(self, data, palette, lang, heading, body):
        self.data, self.p, self.L = data, palette, lang
        self.meta = data["meta"]
        self.heading, self.body = heading, body
        self.fmt = Fmt(lang, self.meta.get("currency", "EUR"))
        self.slides = []          # (id, html)
        self.page = 0

    def c(self, key):
        return "#" + self.p[key]

    def add(self, sid, inner, bg="bg", ink="ink", notes=None, footer=True,
            layout=None):
        self.page += 1
        layout = layout or {}
        sec = style(background=self.c(bg), color=self.c(ink),
                    font_family=self.body,
                    padding=f"{PAD}px {PAD}px {PAD_FOOT if footer else PAD}px",
                    display="flex", flex_direction="column",
                    gap=layout.get("gap", "32px"),
                    justify_content=layout.get("justify"))
        parts = [f'<section id="{sid}" data-transition="fade" style="{sec}">']
        parts += inner
        if footer:
            parts.append(self.footer(ink))
        if notes:
            parts.append(f"<aside>{esc(notes)}</aside>")
        parts.append("</section>")
        self.slides.append((sid, "\n".join(parts) + "\n"))

    def footer(self, ink):
        muted = self.c("invert_muted" if ink == "invert_ink" else "muted")
        left = (f"{self.meta['shop_name']} · {self.meta['period_label']} · "
                + self.L.t("footer.source"))
        if self.meta.get("agency"):
            left += " · " + self.L.t("footer.agency", agency=self.meta["agency"])
        row = style(position="absolute", left=f"{PAD}px", bottom="64px",
                    width=f"{W - 2 * PAD}px", display="flex",
                    flex_direction="row", justify_content="space-between")
        p = style(font_size=f"{SIZE['small']}px", color=muted)
        return (f'<div style="{row}"><p style="{p}">{esc(left)}</p>'
                f'<p style="{p}">{self.page}</p></div>')

    def header(self, title, hint=None):
        """Title, comparison basis on the right, and the reading line."""
        out = []
        row = style(display="flex", flex_direction="row",
                    justify_content="space-between", align_items="baseline",
                    gap="48px")
        h2 = style(font_family=self.heading, font_size=f"{SIZE['title']}px",
                   font_weight="700", line_height="1.1", color=self.c("ink"))
        kick = style(font_size=f"{SIZE['small']}px", color=self.c("muted"),
                     text_align="right")
        kicker = self.meta.get("kicker") or self.meta.get("comparison_sentence")
        out.append(f'<div style="{row}"><h2 style="{h2}">{esc(title)}</h2>'
                   + (f'<p style="{kick}">{esc(kicker)}</p>' if kicker else "")
                   + "</div>")
        if hint:
            out.append(f'<p style="{style(font_size=fs("small"), color=self.c("muted"))}">'
                       f"{esc(hint)}</p>")
        return out

    def card(self, inner, fill="surface", pad=32, extra=None):
        st = style(background=self.c(fill), padding=f"{pad}px",
                   border_radius="16px", display="flex",
                   flex_direction="column", gap="10px", **(extra or {}))
        return f'<div style="{st}">' + "".join(inner) + "</div>"

    def label(self, text, color="muted"):
        st = style(font_size=f"{SIZE['small']}px", font_weight="700",
                   letter_spacing="2px", text_transform="uppercase",
                   color=self.c(color))
        return f'<p style="{st}">{esc(text)}</p>'


# ---------------------------------------------------------------------------
# slides
# ---------------------------------------------------------------------------

def slide_cover(d):
    m, L = d.meta, d.L
    muted = d.c("invert_muted")
    inner = [
        f'<p style="{style(font_size=fs("lead"), color=muted)}">{esc(m["shop_name"])}</p>',
        f'<h1 style="{style(font_family=d.heading, font_size=fs("display"), font_weight="700", line_height="1.05", color=d.c("invert_ink"))}">'
        f'{esc(L.t("cover.title"))}</h1>',
        f'<p style="{style(font_family=d.heading, font_size="72px", font_weight="700", color=d.c("invert_accent"))}">'
        f'{esc(m["period_label"])}</p>',
    ]
    if m.get("comparison_sentence"):
        inner.append(f'<p style="{style(font_size=fs("body"), color=muted)}">'
                     f'{esc(m["comparison_sentence"])}</p>')
    foot = style(position="absolute", left=f"{PAD}px", bottom="64px",
                 width=f"{W - 2 * PAD}px", font_size=f"{SIZE['small']}px",
                 color=muted)
    inner.append(f'<p style="{foot}">'
                 f'{esc(L.t("cover.generated", date=m["generated_on"]))}</p>')
    d.add("cover", inner, bg="invert_bg", ink="invert_ink", footer=False,
          layout={"justify": "center", "gap": "24px"})


def slide_kpis(d):
    kpis = (d.data.get("kpis") or [])[:4]
    if not kpis:
        return
    L, labels = d.L, d.meta.get("comparison_labels") or {}
    cards = []
    for k in kpis:
        inner = [d.label(k["label"]),
                 f'<p style="{style(font_family=d.heading, font_size=fs("value"), font_weight="700", line_height="1.1", color=d.c("ink"))}">'
                 f'{esc(d.fmt.value(k.get("value"), k.get("format", "number")))}</p>']
        for ref_key, ref_label in labels.items():
            txt, sense = d.fmt.delta(k.get("value"), (k.get("compare") or {}).get(ref_key))
            if txt is None:
                continue
            col = d.c("up" if sense > 0 else "down" if sense < 0 else "muted")
            # The sign carries the direction; colour only repeats it.
            inner.append(f'<p style="{style(font_size=fs("small"), color=d.c("muted"))}">'
                         f'<b><span style="color:{col}">{esc(txt)}</span></b> '
                         f'{esc(L.t("common.vs", label=ref_label))}</p>')
        cards.append(d.card(inner, extra={"flex": "1"}))
    row = style(display="flex", flex_direction="row", gap="24px")
    body = [f'<div style="{row}">' + "".join(cards) + "</div>"]
    notes = d.data.get("essentials_notes") or []
    if notes:
        lines = [d.label(L.t("labels.facts"))] + [
            f'<p style="{style(font_size=fs("body"), line_height="1.35", color=d.c("ink"))}">{esc(t)}</p>'
            for t in notes[:3]]
        body.append(d.card(lines, fill="surface_alt"))
    hint = L.t("hints.kpis") if L.has("hints.kpis") else None
    d.add("kpis", d.header(L.t("slides.kpis"), hint) + body)


def _ticks(lo, hi, n=4):
    """Round axis steps covering [lo, hi]."""
    span = max(hi - lo, 1)
    raw = span / n
    mag = 10 ** (len(str(int(raw))) - 1)
    step = next(s * mag for s in (1, 2, 2.5, 5, 10) if s * mag >= raw)
    top = step * -(-hi // step)
    return [i * step for i in range(int(top / step) + 1)]


def slide_trend(d):
    ts = d.data.get("timeseries") or {}
    labels, series = ts.get("labels") or [], ts.get("series") or []
    if not labels or not series:
        return
    L, cur = d.L, d.meta.get("currency", "EUR")
    # Chart box, in slide coordinates. Axis labels are <p>s pinned beside it:
    # fonts never load inside an svg.
    x0, y0, cw, ch = PAD + 120, 330, W - 2 * PAD - 120, 470
    values = [v for s in series for v in s["values"] if v is not None]
    ticks = _ticks(0, max(values))
    top = ticks[-1] or 1
    n = len(labels)

    def px(i):
        return (i / max(n - 1, 1)) * cw

    def py(v):
        return ch - (v / top) * ch

    svg = [f'<svg aria-label="{esc(L.t("slides.trend"))}" width="{cw}" height="{ch}" '
           f'viewBox="0 0 {cw} {ch}" xmlns="http://www.w3.org/2000/svg">']
    for t in ticks:
        y = round(py(t), 1)
        svg.append(f'<line x1="0" y1="{y}" x2="{cw}" y2="{y}" '
                   f'stroke="{d.c("hairline")}" stroke-width="2"/>')
    for i, s in enumerate(reversed(series)):
        idx = len(series) - 1 - i
        pts = " ".join(f"{px(j):.1f},{py(v):.1f}"
                       for j, v in enumerate(s["values"]) if v is not None)
        col = "#" + d.p["series"][idx % len(d.p["series"])]
        dash = ' stroke-dasharray="12 10"' if idx > 0 else ""
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{col}" '
                   f'stroke-width="{5 if idx == 0 else 3}" stroke-linejoin="round"{dash}/>')
    svg.append("</svg>")

    chart = style(position="absolute", left=f"{x0}px", top=f"{y0}px",
                  width=f"{cw}px", height=f"{ch}px")
    inner = d.header(L.t("slides.trend"), L.t("hints.trend") if L.has("hints.trend") else None)
    # Legend: the swatch's stroke (solid or dashed) and the series name say
    # it, not colour alone. Swatches are drawn, never typed: box-drawing
    # characters are missing from most fonts and export as grey squares.
    legend = []
    for i, s in enumerate(series):
        col = "#" + d.p["series"][i % len(d.p["series"])]
        dash = ' stroke-dasharray="12 8"' if i > 0 else ""
        swatch = (f'<svg aria-label="" width="56" height="24" viewBox="0 0 56 24" '
                  f'xmlns="http://www.w3.org/2000/svg"><line x1="0" y1="12" x2="56" y2="12" '
                  f'stroke="{col}" stroke-width="{5 if i == 0 else 3}"{dash}/></svg>')
        legend.append(f'<div style="{style(display="flex", flex_direction="row", align_items="center", gap="12px")}">'
                      f'{swatch}<p style="{style(font_size=fs("small"), color=d.c("muted"))}">{esc(s["name"])}</p></div>')
    inner.append(f'<div style="{style(display="flex", flex_direction="row", gap="40px")}">'
                 + "".join(legend) + "</div>")
    inner.append(f'<div style="{chart}">' + "".join(svg) + "</div>")
    small = f"{SIZE['small']}px"
    for t in ticks:
        inner.append(f'<p style="{style(position="absolute", left=f"{PAD}px", top=f"{y0 + py(t) - 16:.0f}px", width="104px", font_size=small, color=d.c("muted"), text_align="right")}">'
                     f'{esc(L.money(t, cur, short=True) if t else "0")}</p>')
    step = max(1, n // 6)
    for j in range(0, n, step):
        inner.append(f'<p style="{style(position="absolute", left=f"{x0 + px(j) - 40:.0f}px", top=f"{y0 + ch + 12}px", width="80px", font_size=small, color=d.c("muted"), text_align="center")}">'
                     f'{esc(labels[j])}</p>')
    caption = ts.get("caption")
    if caption:
        inner.append(f'<p style="{style(position="absolute", left=f"{PAD}px", top=f"{y0 + ch + 64}px", width=f"{W - 2 * PAD}px", font_size=small, color=d.c("muted"))}">'
                     f'{esc(caption)}</p>')
    d.add("trend", inner)


def slide_plan(d):
    prios = d.data.get("priorities") or []
    if not prios:
        return
    L = d.L
    rows = []
    for c in prios:
        left = [d.label(L.t("labels.priority", n=c["rank"]), color="accent_line"),
                f'<h3 style="{style(font_family=d.heading, font_size="40px", font_weight="700", line_height="1.15", color=d.c("ink"))}">{esc(c["title"])}</h3>',
                f'<p style="{style(font_size=fs("small"), line_height="1.3", color=d.c("muted"))}">{esc(c["finding"])}</p>']
        right = [d.label(L.t("labels.goal")),
                 f'<p style="{style(font_size="30px", font_weight="700", line_height="1.2", color=d.c("ink"))}">{esc(c["goal"])}</p>',
                 f'<p style="{style(font_size=fs("small"), font_weight="700", color=d.c("ink"))}">'
                 f'{esc(L.t("labels.gain_line", label=c["gain_label"], value=c["gain_txt"]))}</p>',
                 f'<p style="{style(font_size=fs("small"), color=d.c("muted"))}">'
                 f'{esc(L.t("labels.reference", reference=c["reference"]))}</p>']
        col = lambda parts, flex: (  # noqa: E731
            f'<div style="{style(flex=flex, display="flex", flex_direction="column", gap="8px")}">'
            + "".join(parts) + "</div>")
        rows.append(d.card([f'<div style="{style(display="flex", flex_direction="row", gap="48px")}">'
                            + col(left, "3") + col(right, "2") + "</div>"], pad=28))
    inner = d.header(L.t("slides.plan"), L.t("hints.plan"))
    inner.append(f'<div style="{style(display="flex", flex_direction="column", gap="20px")}">'
                 + "".join(rows) + "</div>")
    # The method caption is too long for the slide at a readable size: it
    # goes in the speaker notes, and the method slide carries it too.
    d.add("plan", inner, notes=L.t("captions.plan"))


PROTOTYPE = [slide_cover, slide_kpis, slide_trend, slide_plan]


def build(data, palette, lang, theme_raw, root):
    warnings = shared.align_to_period(data)
    data.setdefault("meta", {}).setdefault("comparison_labels", {})
    if not data.get("highlights"):
        data["highlights"] = hl_mod.compute(data, lang=lang, errors=warnings)
    if not data.get("priorities"):
        data["priorities"] = pr_mod.compute(data, lang=lang, errors=warnings)
    heading, body, faces = typefaces(theme_raw)
    d = Deck(data, palette, lang, heading, body)
    for gen in PROTOTYPE:
        try:
            gen(d)
        except Exception as exc:
            warnings.append(f"slides.{gen.__name__}: {exc!r}")

    os.makedirs(os.path.join(root, "project", "slides"), exist_ok=True)
    order = [sid for sid, _ in d.slides]
    index = {
        "v": 4,
        "createdOnFiles": {"v": 1, "at": datetime.datetime.now(
            datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
        "lists": "css",
        "title": f"{data['meta']['shop_name']} · {data['meta']['period_label']}",
        "order": order,
        "cover": order[0] if order else None,
        "sections": {"essentials": {"description": lang.t("toc.essentials_blurb"),
                                    "start": order[0]}} if order else {},
        "faces": faces,
        "designSystems": [],
    }
    with open(os.path.join(root, "project", "deck.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    for sid, markup in d.slides:
        with open(os.path.join(root, "project", "slides", f"{sid}.html"), "w",
                  encoding="utf-8") as f:
            f.write(markup)
    return order, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--theme", help="the theme's config/settings_data.json")
    ap.add_argument("--config", help="client overrides (json)")
    ap.add_argument("--lang", help="report language (default: meta.lang, else en)")
    ap.add_argument("--root", required=True, help="folder to write project/ into")
    a = ap.parse_args()

    data = json.load(open(a.data, encoding="utf-8"))
    lang = Lang(a.lang or (data.get("meta") or {}).get("lang") or "en")
    raw = open(a.theme, encoding="utf-8").read() if a.theme and os.path.exists(a.theme) else ""
    over = json.load(open(a.config, encoding="utf-8")) if a.config and os.path.exists(a.config) else {}
    palette = build_palette(raw, over.get("brand") if "brand" in over else over)
    if over.get("agency") is not None:
        data.setdefault("meta", {})["agency"] = over["agency"]
    order, warnings = build(data, palette, lang, raw, a.root)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    print(json.dumps({"root": a.root, "lang": lang.code, "slides": order,
                      "files": ["project/deck.json"] + [f"project/slides/{s}.html" for s in order],
                      "warnings": warnings}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
