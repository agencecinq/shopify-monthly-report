"""
The Slides backend writes files that follow the Slides type's format: one
<section> per file, inline styles only, no text under 24px.

    python3 -m pytest tests
"""

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "trente", "scripts"))

import build_slides  # noqa: E402
from brand import build_palette  # noqa: E402
from i18n import Lang  # noqa: E402

# Checked on the markup's tags and style attributes, never on the slide text.
FORBIDDEN_TAG = re.compile(r"<style|<script|\sclass=|\son\w+=")
FORBIDDEN_CSS = re.compile(r"(^|;)\s*(margin|z-index)\s*:|var\(|\d(em|rem)\b")


@pytest.fixture(params=["en", "fr"])
def deck(request, tmp_path):
    with open(os.path.join(ROOT, "examples", "report.example.json"), encoding="utf-8") as f:
        data = json.load(f)
    with open(os.path.join(ROOT, "examples", "settings_data.example.json"), encoding="utf-8") as f:
        theme = f.read()
    order, warnings = build_slides.build(data, build_palette(theme),
                                         Lang(request.param), theme, str(tmp_path))
    return tmp_path, order, warnings


def test_index_lists_every_slide(deck):
    root, order, warnings = deck
    assert warnings == []
    index = json.load(open(root / "project" / "deck.json", encoding="utf-8"))
    assert index["v"] == 4 and index["order"] == order and index["cover"] == "cover"
    assert sorted(os.listdir(root / "project" / "slides")) == sorted(f"{s}.html" for s in order)
    for face in index["faces"].values():
        assert face["href"].startswith("https://fonts.googleapis.com/css2?")


def test_slides_follow_the_format(deck):
    root, order, _ = deck
    for sid in order:
        markup = (root / "project" / "slides" / f"{sid}.html").read_text(encoding="utf-8")
        assert markup.startswith(f'<section id="{sid}"') and markup.rstrip().endswith("</section>")
        assert markup.count("<section") == 1
        assert not FORBIDDEN_TAG.search(markup), sid
        for css in re.findall(r'style="([^"]*)"', markup):
            assert not FORBIDDEN_CSS.search(css), (sid, css)
        sizes = [int(s) for s in re.findall(r"font-size:(\d+)px", markup)]
        assert sizes and min(sizes) >= 24, sid
        assert len(re.findall(r"<(?!/)[a-z]", markup)) <= 200, sid


def test_no_symbol_glyphs(deck):
    # Box drawing, blocks, geometric shapes and dingbats are missing from most
    # typefaces and export as grey squares: swatches and marks are drawn.
    root, order, _ = deck
    for sid in order:
        markup = (root / "project" / "slides" / f"{sid}.html").read_text(encoding="utf-8")
        bad = {c for c in markup if 0x2500 <= ord(c) <= 0x27BF}
        assert not bad, (sid, bad)
