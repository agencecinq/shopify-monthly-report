# Trente

The monthly Shopify report, by [CINQ](https://agencecinq.com).

Trente is a free, open-source Claude plugin that turns a Shopify store's data into a complete monthly
report: a PowerPoint deck in the store's own colours, ending with next month's
plan of measured targets.

It is built for the merchant, not the analyst. It picks the chapters that make
sense for that particular store, surfaces what stands out, and says what to
work on next, in figures anyone can check.

[Français](README.fr.md)

![The month ahead](docs/plan.png)

## What makes it different

**It adapts to the store.** Before collecting a single figure, it works out the
catalogue structure, the sales channels, the countries, whether there are
subscriptions or a point of sale, and whether customers come back. A store that
sells consumables gets its Customers chapter second; a store that sells durable
goods gets Acquisition second. A 15-product catalogue is detailed down to sizes
and colours; a 2,000-product catalogue is presented by product line.

**It prioritises without advising.** The plan ranks workstreams by what they are
worth in money, sets a target for each, and calculates the gain: "bringing the
refund rate from 10.0% to 8.0% keeps 900 of sales per month at current volume".
Every target is set for next month and names where it comes from: the best
level the store reached in the last six months, capped at a one-tenth
improvement when that month is old and out of reach; a threshold the merchant
declared; the reference period; or, failing all of these, a stated convention.

**It never states a cause.** No slide says why a number moved, and none
prescribes a remedy. There is no industry benchmark anywhere: everything rests
on what a line costs, on the store measured against itself, and on thresholds
the merchant declared.

**It remembers.** The context and the plan are stored in a metafield on the
store itself. Next month's report opens on a follow-up slide comparing each
target to what was actually measured: every commitment the plan makes is
checked, a month later.

**Your data stays in your account.** Figures are read through the Shopify
connector and processed in your Claude account. The plugin makes no network call
of its own, and nothing reaches CINQ.

## Requirements

- The **Shopify connector** in Claude.
- **Python 3.9+ with [python-pptx](https://python-pptx.readthedocs.io/)**, a
  hard dependency: the deck is a PowerPoint file and python-pptx builds it.
  Without it no report is produced, and Claude says so before collecting any
  data. In Claude Code it installs with `pip`; in Claude Desktop and claude.ai,
  the environment Claude runs code in must have it or be able to install it.
- **Pillow**, optional: it only places the store's logo on the cover. Without
  it the deck ships without a logo, and the build says so.

Email, analytics and advertising connectors are optional. When they are absent
the matching chapters simply do not appear, with no gap and no "not available".

## Install

The repository is its own plugin marketplace. In Claude Code, add it and then
install the plugin:

```
/plugin marketplace add agencecinq/shopify-monthly-report
/plugin install trente@agencecinq
```

The two steps are separate on purpose: the first tells Claude where to look,
the second installs. Restart the session afterwards so the skill loads.

Then the Python dependencies the deck is built with:

```bash
pip install python-pptx Pillow
```

## Use

Ask in one sentence:

- "Build me last month's report"
- "September figures as a deck"
- "A recap of the quarter for my co-founder"
- "What should I focus on?"

With no period given, the report covers the last complete calendar month.

The first time on a store, six questions are asked one at a time: who reads the
report, what the store sells, the revenue target for the year, whether cost of
goods is filled in, what return rate is considered acceptable, and which
channels to leave out. The answers live in the store's Shopify metafield, so
there is no file to keep. After that, one extra question per month, no more.

## What the report contains

![What stands out this month](docs/highlights.png)

Cover, table of contents, the month at a glance, what stands out, last month's
plan, the month ahead, then the chapters: **Sales** (daily trend, 24-month
history, breakdown, channels), **Acquisition** (funnel, sources, countries and
devices), **Products** (best sellers, lines, variants, stock, returns),
**Customers**, **Profitability**, **Marketing**, a method slide saying where
every figure comes from, and a closing slide on Trente and CINQ with a link to
reach us.

Each chapter carries one line explaining what the metric measures and how to
read it. Chapters with no data are not rendered.

## Languages

English and French ship with the plugin. Pass `--lang en`, `--lang fr`, or set
`meta.lang` in the report data.

Number and currency formatting follows the language, not just the words: French
writes `35 396 €` and English writes `€35,396`.

To add a language, copy `skills/trente/i18n/en.json`, translate
the values, keep the keys, and adjust the `_format` block. Pull requests
welcome. Any key a translation is missing falls back to English rather than
printing a raw key into someone's deck.

## Try it without a Shopify store

The repository ships a complete example built on a fictional store:

```bash
cd skills/trente/scripts
python3 build_report.py --data ../../../examples/report.example.json \
  --lang en -o report.pptx
```

That file is also the reference for the data contract, documented in
[`report-schema.md`](skills/trente/references/report-schema.md).

## How it works

Claude collects the data and writes a `report.json`; three Python scripts turn
it into the deck. The split matters: everything that must be reproducible is in
the scripts, not in the model's output.

| File | Role |
|---|---|
| `scripts/brand.py` | Derives a readable palette from the Shopify theme, handling the three families of themes and fixing contrast |
| `scripts/highlights.py` | Computes the salience findings from numeric rules |
| `scripts/priorities.py` | Builds next month's plan: ranking, targets, follow-up |
| `scripts/build_report.py` | Assembles the deck |
| `scripts/i18n.py` | Language and number formatting |

Findings and targets are computed, never written by the model. That is what
keeps them reproducible from one month to the next and from one store to
another, and what stops the report drifting into advice.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Translations, new salience rules and
support for other analytics sources are all welcome.

## Licence

MIT, see [LICENSE](LICENSE). Built by [CINQ - Agence Wordpress & Shopify](https://agencecinq.com).
