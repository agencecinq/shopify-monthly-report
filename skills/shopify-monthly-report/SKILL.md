---
name: shopify-monthly-report
description: >
  Builds a complete monthly performance report for a Shopify store as a
  PowerPoint deck in the store's own colours: sales, traffic, conversion,
  products, customers, margin, returns and stock, followed by a 90-day plan
  with measured targets. Adapts to the store's profile and handles several
  stores. Use whenever someone asks for their monthly report, their reporting,
  their month's figures, their numbers, their priorities for the quarter, or
  says "build me the September report", "how is my store doing this month", "a
  recap for my co-founder", "last month's figures as a deck", "what should I
  focus on". Also use for a quarter or any other period whenever the request is
  for a figures-based review of the store.
---

# Shopify monthly report

Build a complete report on a Shopify store's performance, composed around what
that store actually is, dressed in its theme's colours, and closed by a costed
action plan.

The aim is to do the reader's work for them: they should open the document and
see immediately what matters and what to work on.

## The governing rule

The report **selects, orders, surfaces and prioritises**. It never explains
causes.

**Allowed**

- Choosing the chapters that make sense for this store, and ordering them.
- Putting two measured figures side by side: "traffic rises 7.3% while revenue
  falls 10.4%".
- Surfacing what stands out: "three products make 61% of gross sales".
- Ranking workstreams by what they are worth in money, and setting a target
  whose gain is calculated.
- Explaining what a metric measures and how to read it.

**Forbidden**

- Stating a cause: "the drop comes from SEO".
- Prescribing a means: "rewrite the product pages", "restart your campaigns".
  The report says where to return to and what it is worth, not how.
- Judging: "a good month", "a worrying rate", "this rate is normal".
- Comparing to an industry benchmark. A priority rests on what a line is worth
  in money, on the store degrading against itself, or on a structural
  dependency. Never on "the market does better".

Never invent, estimate or extrapolate a figure. Data that is unavailable is
absent from the report.

If the user asks for causes or for means, give them in the conversation, marking
clearly what is measured and what is a hypothesis.

## Language

The deck's own wording comes from `i18n/<lang>.json`; `en` and `fr` ship with
the plugin. Pass the language with `--lang`, or set `meta.lang` in report.json.

**Everything that comes from the data must be written in that same language.**
Labels, period names, comparison labels, `essentials_notes`, `customers.note`
and `methodology` are produced by you, not by the catalogue. A French deck with
English country names reads as broken.

To add a language, copy `i18n/en.json`, translate the values, and keep the keys
and the `_format` block, which carries number and currency conventions.

## Procedure

### 1. Identify the store

Call `get-shop-info`: name, domain, currency, time zone.

With no Shopify tool available, say the store has to be connected in the
connector settings, and stop there.

If the request concerns a store other than the connected one, follow the
"Several stores" section of `references/context.md`.

### 2. Read the context, or establish it

Follow `references/context.md`.

Read the `shopify_report.context` metafield on the store.

- **Absent**: this is the first time. Create the metafield definition so the
  merchant can see and correct their context, then run the opening
  questionnaire, six questions asked one at a time, before collecting anything.
- **Present**: take it up, confirm in one sentence what is on file, and ask the
  month's enrichment question.

Check that the context matches the connected store.

### 3. Set the period and the comparisons

Default: the **last complete calendar month**.

| History before the period | Comparisons |
|---|---|
| under 2 months | none, standalone values |
| 2 to 12 months | previous month |
| 13 months or more | previous month **and** same month last year |

On a seasonal business, present the year-on-year comparison as the primary one
in `comparison_sentence`. Write the comparison basis out in full: it appears on
every slide.

### 4. Profile the store

Follow `references/profiling.md`: catalogue structure, sales model, what drives
the business, seasonality. Fill in `profile`.

This step decides which chapters make up the report.

### 5. Collect the data

Follow `references/collecting-data.md`.

**The analytics API rate-limits.** Two queries at a time at most. On a "Rate
limited" error, wait a few seconds and re-run that query alone.

Do not skip the two twelve-month histories (returns and conversion): without
them the plan has no reference and cannot set a target.

### 6. Extract the store's colours

Follow `references/collecting-data.md`, "Branding" section. Read the published
theme's `config/settings_data.json`, save it as is, fetch the logo. If the theme
is unreachable, carry on without it.

### 7. Add other sources, if they are there

Check for email and SMS tools, audience analytics and advertising, by calling
one of their tools, never by assuming.

A section with no data does not appear. Never produce an empty slide.

### 8. Write report.json

Build the file per `references/report-schema.md`.

Write `essentials_notes`, `customers.note` and `methodology` following
`references/writing-rules.md`.

**Write neither `highlights` nor `priorities`.** The scripts compute them from
numeric rules, which keeps findings and targets reproducible, free of judgement,
and safe from drifting into advice.

Check:

- Every figure comes from an API response.
- Percentages are fractions (0.0109, not 1.09).
- Labels are written in the report's language and ready to read.
- The online store channel carries `"online": true`.
- `context` and `previous_plan` are taken from the metafield.

### 9. Build the deck

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/shopify-monthly-report/scripts/build_report.py" \
  --data report.json \
  --theme settings_data.json \
  --logo logo.png \
  --config config.json \
  --state plan.json \
  --lang fr \
  -o "Report <Store> - <Month Year>.pptx"
```

`--theme`, `--logo`, `--config` and `--lang` are optional. `--state` writes the
plan to a file, to be stored back in the metafield at the next step.

Dependencies, to install if the import fails:

```bash
pip install python-pptx Pillow --break-system-packages
```

The script prints the palette it used, the chapters, the findings and the plan.

### 10. Store the context and the plan

Write the updated context to the `shopify_report.context` metafield, with
`previous_plan` set to the contents of the `--state` file.

Without this step, next month's report cannot measure the milestones, and the
plan stays an intention nobody ever checks. This is what separates a report
from a follow-up.

If the write fails for lack of permission, say so and offer to keep the context
in a file. Never block delivery over it.

### 11. Check, then deliver

Verify five things:

1. The totals match the API responses.
2. No slide states a cause, a means or a judgement.
3. The comparison basis appears on the slides.
4. The chapters match what the store actually is.
5. The plan's targets are levels already reached, or explicitly capped.

Deliver the file, then summarise: the profile used, the period, revenue and its
change, the two or three priorities with their calculated gain, and any missing
sources.

## What the report contains

The script composes on its own from the data present and the profile.

1. Cover
2. Table of contents (past 8 content slides)
3. The month at a glance: four indicators and their changes
4. What stands out this month: the salience findings
5. Where last month's plan stands (when a previous plan exists)
6. The next 90 days
7. **Sales**: daily trend, 24-month history, breakdown, channels
8. **Acquisition**: funnel and sources, traffic by country and device, sales by country
9. **Products**: best sellers, product lines, variants, stock, returns
10. **Customers**: new and returning
11. **Profitability**: gross margin
12. **Marketing**: email and SMS, advertising
13. Method and scope

Profile `retention` lifts the Customers chapter to just after Sales; profile
`acquisition` lifts Acquisition. Any chapter without data disappears, divider
included.

## How the plan is built

The scripts sort workstreams into two natures that are never mixed:

- **leaks**, where money walks out and can be recovered: conversion, refunds,
  margin, average order value;
- **risks**, where a dependency should be reduced: catalogue concentration,
  reliance on one source.

Leaks come first. At most one risk enters the plan, otherwise it stops being
actionable. A workstream whose monthly gain is worth less than 2% of revenue is
dropped: two priorities beat a list.

A workstream's target is a level the store actually reached in the last six
months. If that level is more than two months old, the target is capped at a
three-tenths improvement: a metric degrading for six months would otherwise
produce a goal nobody can hold. A threshold declared by the merchant in the
context beats this internal reference.

## Client configuration

An optional `config.json` forces the palette, the language and the agency name.
Template in `assets/config.example.json`. Not to be confused with the context,
which lives in the store's metafield.

On fonts: only name a brand font if the person opening the deck has it
installed.

## Periods other than a month

- Past 62 days, use `TIMESERIES week` rather than `day`.
- Adapt `period_label` and `comparison_labels`.
- The history chapter and the plan stay monthly.

## Mistakes to avoid

- Filling a context field without an explicit answer from the user. A supposed
  value becomes indistinguishable from a declared one and drives the plan's
  targets for months. An unanswered field stays `null`.
- Producing a report without reading the store's context, or without
  establishing it the first time.
- Forgetting to store the plan back in the metafield: next month's follow-up
  becomes impossible.
- Merging two stores' figures into one report.
- Writing findings or the plan by hand when the scripts compute them.
- Publishing a profitability chapter when cost of goods is not filled in: the
  margin is then wrong, and wrong in the flattering direction.
- Producing an empty slide because a source is missing.
- Showing a change without naming the reference period.
- Comparing an incomplete month to a complete one without saying so.
- Confusing orders with checkouts completed on the online store.
- Dropping the negative sign the API returns on discounts and refunds.
