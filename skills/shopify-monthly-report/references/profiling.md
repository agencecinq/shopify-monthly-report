# Profiling the store

Profiling works out what the API can tell you. It decides which chapters make
up the report, in what order, and how some findings are worded. It never
changes a figure.

Without it, a wine merchant selling consumables and a furniture maker selling
once in a lifetime get the same report. Neither opens the document with the
same question in mind.

## What to establish

### 1. Catalogue structure

```graphql
query { productsCount { count } }
```

```
FROM sales SHOW gross_sales, orders GROUP BY product_type
ORDER BY gross_sales DESC LIMIT 10 SINCE START UNTIL END
```

```
FROM sales SHOW gross_sales GROUP BY product_variant_title
ORDER BY gross_sales DESC LIMIT 12 SINCE START UNTIL END
```

What to draw from it:

| Finding | Effect on the report |
|---|---|
| Fewer than 30 products | Product detail is exhaustive and worth having. The variants chapter earns its place: on a narrow catalogue the real variety is in sizes and colours. |
| 30 to 300 products | Lead with product lines; keep the top products as a complement. |
| More than 300 products | A top 10 is anecdotal. Prefer product lines, and present the top products as an extract, never as a panorama. |
| One product line, or none set | Skip the lines chapter rather than showing a single bar at 100%. |
| Variant labels empty or equal to the product name | Skip the variants chapter: the catalogue has no real variants. |

### 2. Sales model

```
FROM sales SHOW orders, total_sales GROUP BY sales_channel
ORDER BY total_sales DESC LIMIT 10 SINCE START UNTIL END
```

```
FROM sales SHOW orders, total_sales GROUP BY billing_country
ORDER BY total_sales DESC LIMIT 8 SINCE START UNTIL END
```

```graphql
query {
  locations(first: 10) { nodes { name isActive } }
  sellingPlanGroups(first: 3) { nodes { name } }
}
```

What to draw from it:

- **Several sales channels**: add the channels chapter, and above all explain in
  the methodology that the conversion funnel covers the online store only. This
  is the single biggest source of confusion when a merchant reads their report.
- **`sellingPlanGroups` not empty**: the store sells by subscription. Repeat
  purchase is structural, not a loyalty signal. The profile is necessarily
  `retention`.
- **Several active locations, or a point-of-sale channel**: always separate
  online from physical. Never mix the two in one conversion rate.
- **One country above 90% of sales**: skip the sales-by-country chapter, it
  teaches nothing. Keep it as soon as a second country passes 5%.

### 3. What drives the business

This is the most structural decision. It rests on two figures:

```
FROM sales SHOW new_customers, returning_customers, returning_customer_rate
SINCE START UNTIL END
```

| Condition | `profile.driver` |
|---|---|
| Active subscriptions | `retention` |
| Returning customer rate ≥ 25% | `retention` |
| Returning customer rate < 25% | `acquisition` |

This field reorders the chapters:

- `retention`: Sales, **Customers**, Products, Acquisition, Profitability, Marketing
- `acquisition`: Sales, **Acquisition**, Products, Customers, Profitability, Marketing

On an `acquisition` store, fill `customers.note` with one sentence saying the
product is not renewed in the short term. This is the only place in the report
where the profile speaks in words, and it stays descriptive: write "a buyer
does not renew this purchase in the short term", not "this rate is normal",
which would be a judgement.

Compute the rate on the period, but check it against the two or three preceding
months before deciding: a single month can be atypical.

### 4. Seasonality

```
FROM sales SHOW total_sales, orders TIMESERIES month SINCE -24m UNTIL today
```

This one query serves three purposes at once:

1. It establishes how much history exists, and therefore which comparisons are
   possible.
2. It feeds the "month in context" chapter.
3. It says whether the business is seasonal.

Spotting seasonality: if a year's strongest month is more than twice its
weakest, the business is seasonal. The year-on-year comparison then becomes the
primary one, and the month-on-month comparison should be presented as secondary
in `comparison_sentence`.

With less than 6 months of history, skip the history chapter.

## What the profile never does

The profile composes the report; it does not comment on the figures.

It does not justify a result. "The repeat rate is low because the product
lasts" is an explanation, and therefore banned from the document. What the
profile does allow is not putting retention on page 3 of a helmet brand's
report, and stating the nature of the product factually in the customers
chapter note.

It does not change the salience thresholds either. The rules in
`scripts/highlights.py` are the same for every store, which keeps findings
comparable from month to month and from client to client.

## Where to write it

In `report.json`, under `profile`. Only `driver` is read by the script; the
rest documents the decision and helps write the notes.

```json
{
  "catalogue": {"active_products": 24, "product_lines": 3,
                "variants_per_product": "size / colour"},
  "model": {"channels": ["Online Store", "Draft Orders", "Faire"],
            "subscriptions": false, "locations": 1, "billing_countries": 6},
  "driver": "acquisition",
  "cycle": "durable goods, low repeat purchase expected",
  "seasonal": true,
  "summary": "Single-category leather goods brand, narrow catalogue declined in colours, mostly domestic sales through the online store, with a wholesale channel alongside."
}
```

State the profile you settled on in your reply to the user, in one sentence. If
it is wrong, that is the first thing they will correct, and the correction
ripples through the whole report.
