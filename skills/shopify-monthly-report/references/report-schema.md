# report.json structure

The data contract between collection and the deck builder.

**Any section that is absent or `null` is simply skipped.** That is how the deck
adapts: never supply a section full of zeros to "fill it in".

Only `meta` and `kpis` are required.

All examples use a made-up store, Marlow Goods, with made-up figures.

## Conventions

| Type | Expected form | Example |
|---|---|---|
| Amount | number, store currency, no symbol | `42000.00` |
| Percentage | **fraction**, never hundredths | `0.0145` for 1.45% |
| Integer | number | `260` |
| Label | in the report's language, ready to display | `"Direct or unidentified"` |

Discounts and refunds in `sales_detail` keep the **negative sign** the API
returns. Everywhere else (`returns`), use absolute values.

## meta (required)

```json
{
  "shop_name": "Marlow Goods",
  "shop_domain": "www.marlowgoods.com",
  "currency": "EUR",
  "lang": "en",
  "period_label": "August 2026",
  "period_start": "2026-08-01",
  "period_end": "2026-08-31",
  "generated_on": "14 September 2026",
  "agency": null,
  "comparison_labels": {
    "previous_period": "July 2026",
    "previous_year": "August 2025"
  },
  "comparison_sentence": "Compared with July 2026 and August 2025"
}
```

`lang` selects the language catalogue; `--lang` on the command line overrides
it. `comparison_labels` drives the change lines on the KPI cards: a missing key
removes its line. With no comparison, pass an empty object.

`agency` is optional and adds a discreet line in the slide footer. It can also
come from `config.json`.

## kpis (required)

Four entries at most, shown in the order given.

```json
[
  {"key": "total_sales", "label": "Revenue", "value": 42000.00,
   "format": "money",
   "compare": {"previous_period": 46800.00, "previous_year": 31500.00}},
  {"key": "orders", "label": "Orders", "value": 260, "format": "number",
   "compare": {"previous_period": 291, "previous_year": 198}},
  {"key": "aov", "label": "Average order value", "value": 161.54,
   "format": "money", "compare": {"previous_period": 160.82}},
  {"key": "cr", "label": "Conversion rate", "value": 0.0145,
   "format": "percent", "compare": {"previous_period": 0.0172}}
]
```

`key` must stay as shown: the salience and priority engines look these up.
`format` is `money`, `number`, `percent` or `decimal`.

## essentials_notes

Two or three descriptive findings under the KPI cards. See `writing-rules.md`.

## timeseries

```json
{
  "labels": ["1", "2", "3"],
  "series": [
    {"name": "August 2026", "values": [1420.50, 980.00, 2210.75]},
    {"name": "July 2026", "values": [1180.00, 1640.20, 890.00]}
  ],
  "caption": "Daily revenue, taxes and shipping included."
}
```

The first series is the current period and gets the solid line; the rest are
dashed. Every series must match `labels` in length. Negative values are
accepted and displayed.

## funnel

```json
{"sessions": 17900, "cart": 690, "checkout": 430, "purchase": 232}
```

Use `sessions_that_completed_checkout` for `purchase`, **not** the order count:
the rest of the funnel only covers the online store.

## traffic_sources

```json
[{"label": "Direct or unidentified", "orders": 148, "sales": 24100.00}]
```

Sorted by sales descending; six entries shown at most.

## customers

```json
{"new": 201, "returning": 52, "total": 253, "returning_rate": 0.2055,
 "repeat_rate": null, "days_to_second_order": null,
 "note": "On a durable product, a buyer does not renew this purchase in the short term."}
```

`note` is the only place in the report where the store's profile speaks in
words. Describe the product, never judge the rate.

## margin

```json
{"gross_profit": 21400.00, "cogs": 16900.00, "net_sales": 38300.00,
 "margin_rate": 0.5587, "compare_margin_rate": 0.5720,
 "incomplete": "Cost of goods is filled in on 34 of 41 products."}
```

Omit the whole section if costs are not filled in. `compare_margin_rate` adds a
comparison line and feeds the margin workstream.

## sales_detail

```json
{
  "gross_sales": 45000.00, "discounts": -2200.00, "sales_reversals": -4500.00,
  "net_sales": 38300.00, "shipping_charges": 700.00, "taxes": 3000.00,
  "total_sales": 42000.00,
  "compare": {"gross_sales": 48900.00, "discounts": -1900.00,
              "sales_reversals": -3800.00}
}
```

`compare` is optional, line by line. For discounts and refunds the change is
measured on the amount; the script handles it provided the signs are kept.

## top_products

```json
[{"label": "Weekender Bag", "sales": 12400.00, "orders": 62}]
```

## returns

```json
{
  "amount": 4500.00,
  "rate": 0.10,
  "orders": null,
  "top": [{"label": "Weekender Bag", "amount": 1850.00}]
}
```

Amounts as **absolute values**. `rate` is refunds over gross sales.

## devices and countries

```json
[{"label": "Mobile", "sessions": 13100, "conversion_rate": 0.0121}]
```

```json
[{"label": "United Kingdom", "sessions": 11200}]
```

## inventory

```json
[{"label": "Card Holder", "sold": 88, "ending_units": 210, "sell_through": 0.2954}]
```

## channels

```json
[{"label": "Online store", "orders": 232, "sales": 36100.00, "online": true},
 {"label": "Manual orders", "orders": 19, "sales": 4100.00},
 {"label": "Faire", "orders": 9, "sales": 1800.00}]
```

`online: true` on the online store channel is **required** as soon as there is
more than one channel: the label is translated, so it is the only way to tell
online sales from the rest. The chapter appears from two channels.

## categories

Sales by product line, from Shopify's product type field. Drop the row with an
empty label. Appears from two lines.

```json
[{"label": "Bags", "sales": 28900.00, "orders": 131}]
```

## variants

Best-selling variants. Appears from three entries. Omit the section when labels
are empty or identical to the product name.

```json
[{"label": "Weekender Bag / Tan", "sales": 6200.00}]
```

## sales_by_country

Sales by billing country, distinct from `countries`, which covers sessions.
Appears from two countries.

```json
[{"label": "United Kingdom", "orders": 198, "sales": 33200.00}]
```

## seasonality

Monthly history, oldest first. The last entry must be the period under review:
that is the bar the chart highlights.

```json
[{"label": "Aug 26", "value": 42000.00}]
```

Short labels in the report's language, or the axis becomes unreadable. Six
months minimum for the chapter to appear, twelve for the rank to be computed.

## history

Monthly histories over twelve months. **Without these the plan has no reference
and cannot set a target.**

```json
{
  "returns": [{"label": "Aug 26", "gross_sales": 45000.00, "reversals": -4500.00}],
  "conversion": [{"label": "Aug 26", "sessions": 17900, "conversion_rate": 0.0145}]
}
```

`reversals` keeps the API's negative sign. Months at exactly zero are dropped
from the reference: they almost always mean returns were not being recorded
yet.

## sessions_compare

Sessions for the period and its references. Feeds the finding that sets traffic
against revenue.

```json
{"value": 17900, "previous_period": 16400, "previous_year": 12100}
```

## context

Store context, taken from the metafield. See `context.md`.

```json
{"audience": "founder", "activity": "Leather bags and small goods.",
 "annual_revenue_target": 480000, "cost_of_goods": "partial",
 "acceptable_return_rate": 0.08, "excluded_channels": []}
```

`acceptable_return_rate` beats the internal reference when setting the refunds
target.

## ytd

Year to date against target, when the merchant declared one.

```json
{"value": 268400.00, "target": 480000, "months_elapsed": 8}
```

## previous_plan

Last month's plan, taken from `context.previous_plan`. Never compose it by
hand: it is the file written by the previous report's `--state` option.

## profile

See `profiling.md`. Only `driver` is read by the script; it is `"acquisition"`
or `"retention"` and reorders the chapters.

## klaviyo and ads

Generic sections, one per additional source.

```json
{
  "chart_title": "Attributed revenue",
  "chart": [{"label": "Flows", "value": 8420.00},
            {"label": "Campaigns", "value": 3110.00}],
  "rows": [{"label": "Share of total revenue", "value": "27.4%"},
           {"label": "Average open rate", "value": "41.2%"}],
  "caption": "Klaviyo attribution over 5 days after open or click."
}
```

`rows[].value` is an **already formatted string**: the script prints it as is.
`chart` values are numbers, shown in the store currency. State the attribution
window in `caption`, or the figures cannot be compared with Shopify's.

## highlights and priorities

**Do not fill these in.** The scripts compute them from numeric rules.
Supplying them by hand loses the guarantee that every target is reachable and
every gain checkable. Fill them only if the user explicitly asks to force a
finding.

## lectures

Overrides for the reading line under each slide title. The language catalogue
supplies one per chapter; only name the ones to replace.

```json
{"margin": "What is left once cost of goods is deducted, before shipping."}
```

Available keys: `kpis`, `highlights`, `plan`, `follow_up`, `trend`,
`seasonality`, `sales_detail`, `channels`, `acquisition`, `traffic`,
`sales_country`, `top_products`, `categories`, `variants`, `inventory`,
`returns`, `customers`, `margin`, `klaviyo`, `ads`, `methodology`.

## methodology

Six to eight blocks. See `writing-rules.md`. Keep `text` under 220 characters,
or the two columns overflow.

```json
[{"title": "Period and time zone",
  "text": "1 to 31 August 2026, in the store's time zone."}]
```
