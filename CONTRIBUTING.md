# Contributing

Thanks for looking. This plugin is used in production on real client reports,
so the bar is about correctness rather than features: a wrong figure in a deck
that goes to a merchant's board is worse than a missing chapter.

## Ground rules

The report **never states a cause and never prescribes a means**. It selects,
orders, surfaces and prioritises. A contribution that makes it say "the drop
comes from X" or "you should do Y" will not be merged, however useful it seems.

There is **no industry benchmark** anywhere. A priority rests on what a line is
worth in money, on the store measured against itself, or on a structural
dependency. Any rule needing an outside reference belongs somewhere else.

Findings and targets are **computed, not written**. They live in
`scripts/highlights.py` and `scripts/priorities.py` so the same data always
produces the same output. Please do not move that work into the prompt.

## Setting up

```bash
pip install python-pptx Pillow
cd skills/shopify-monthly-report/scripts
python3 build_report.py --data ../../../examples/report.example.json \
  --lang en -o /tmp/report.pptx
```

The example is a fictional store. Never commit real store data, in any file,
including issues: revenue, product names and domains identify a business.

## Adding a language

1. Copy `skills/shopify-monthly-report/i18n/en.json` to `<code>.json`.
2. Translate the values, keep every key.
3. Adjust `_format`: thousands separator, decimal separator, currency position
   and spacing, spacing before the percent sign.
4. Check the key sets match:

```bash
python3 - <<'EOF'
import json
def flat(d, p=""):
    out=set()
    for k,v in d.items():
        if k.startswith("_"): continue
        out |= flat(v, f"{p}{k}.") if isinstance(v, dict) else {f"{p}{k}"}
    return out
a=flat(json.load(open("skills/shopify-monthly-report/i18n/en.json")))
b=flat(json.load(open("skills/shopify-monthly-report/i18n/xx.json")))
print("missing:", sorted(a-b), "| extra:", sorted(b-a))
EOF
```

5. Build in your language and read every slide. Number formatting is where
   translations usually break, not wording.

A missing key falls back to English rather than printing a raw key, so a
partial translation is safe to ship.

## Adding a salience rule

A rule goes in `scripts/highlights.py`, returns `{tag, text, score}`, and must:

- be computable from `report.json` alone, with no extra call;
- state a measured fact, never a cause or a judgement;
- carry a threshold that keeps it quiet on a store where nothing is happening;
- take all its wording from the language catalogue.

Add the strings to both `en.json` and `fr.json`, and pick a `tag` that does not
collide: only one finding per tag makes the slide.

## Adding a workstream to the plan

A workstream goes in `scripts/priorities.py` and must declare its `nature`:

- `leak` — money leaving that can be recovered;
- `risk` — a dependency reduced by moving revenue, not by earning it.

The two are ranked separately and never compared. A workstream needs a target
derived from the store's own history, and a gain that can be checked with a
pencil. If you cannot write the calculation in one sentence, the workstream is
not ready.

## Pull requests

- One subject per pull request.
- Build the example in both languages and say so in the description.
- Run the structure check before pushing:

```bash
python3 tools/validate_plugin.py .
```

- If you changed a layout, attach a screenshot of the slide. Overlaps only show
  up visually.
