# Writing rules

Three pieces of text are written by hand: the findings under the KPI cards
(`essentials_notes`), the customers chapter note (`customers.note`), and the
method slide (`methodology`). Everything else is figures.

The findings on the "what stands out" slide are not written: the script
computes them from numeric rules. Neither are the reading lines under each
title, except to replace one through `lectures`.

Write all of them in the report's language.

## The findings (essentials_notes)

Two or three sentences, one line each. They put measured figures side by side
without explaining them.

### The test

A sentence is acceptable if a reader can verify it from the figures in the
deck. The moment it asserts something the figures do not show, it goes.

| Write | Do not write | Why |
|---|---|---|
| Revenue falls 10.3% vs July 2026 and rises 33.3% vs August 2025. | A mixed month. | "Mixed" is a judgement. |
| Traffic rises 9.1% while conversion moves from 1.72% to 1.45%. | The drop comes from weaker conversion. | "Comes from" is an unproven cause. |
| Refunds account for 4,500, or 10.0% of gross sales. | The return rate is worrying, the product pages need work. | Judgement and prescription. |
| 57% of sales come from unidentified sources. | Organic search is driving growth. | Attribution that was never measured. |

Putting two figures side by side is allowed and wanted: that is what makes a
finding useful. Saying why they moved is not.

### What to keep

Pick findings in this order, stopping at three:

1. The change in revenue and its comparison bases.
2. The sharpest movement among traffic, conversion and average order value.
3. A line that weighs materially: refunds, discounts, concentration on one
   source or one product.

Always put a number in. A sentence without one has no place here.

## The customers chapter note

One or two sentences, only when the nature of the product governs how the
repeat rate should be read. Describe the product, not the result.

| Write | Do not write |
|---|---|
| On a durable product, a buyer does not renew this purchase in the short term. | This repeat rate is normal for this kind of product. |
| The store sells by subscription: repeat purchase comes from renewals. | Strong retention performance. |

On a store whose driver is retention, this note is unnecessary: the customers
chapter already leads the report.

## The method slide (methodology)

Six to eight blocks. This is the slide that makes the report defensible: it
says where the figures come from and what they do not cover.

Blocks to produce every time:

- **Period and time zone** — exact dates, the store's time zone, comparison
  bases.
- **Total sales** — Shopify's formula, spelled out.
- **Conversion funnel** — the funnel covers the online store only.
- **Traffic attribution** — last click, and the fact that visits with no
  referrer fall into direct, which inflates that line.
- **Data source** — Shopify Analytics, the date it was queried, and the fact
  that the Shopify admin may show differences depending on its time zone and
  channel scope.

Conditional blocks, when the case arises:

- **Orders against the funnel** — whenever order count differs materially from
  checkouts completed online. Give both figures and the channel split.
- **Refunds** — a refund is dated when processed, not when the original order
  was placed; a day can therefore be negative.
- **Gross margin** — computed from costs filled in on Shopify; items with no
  cost count as zero, which overstates the margin.
- **Incomplete period** — if the period is not over, say so and give the number
  of days covered.
- **Third-party attribution** — for email or advertising, the attribution
  window, and the fact that those figures overlap Shopify's rather than adding
  to them.

The script appends a **90-day plan** block on its own when a plan is produced,
so there is no need to write one.

Neutral, factual tone. A limitation is described, not apologised for: write
"items with no cost recorded count as zero", not "unfortunately the cost data
is incomplete".

## General style

- No jargon where a plain word exists.
- No emoji.
- No em dash.
- Numbers follow the report language's conventions. The script handles the
  figures it formats; match it in the text you write.
- A change is read against a named reference: always "vs July 2026", never "vs
  last month".

## What belongs in the conversation, not the deck

Causes, hypotheses and the means of acting belong in your reply, never in the
file. If the user asks "what do you make of it", answer plainly in the
conversation, separating what is measured from what is a hypothesis, and leave
the deck factual.
