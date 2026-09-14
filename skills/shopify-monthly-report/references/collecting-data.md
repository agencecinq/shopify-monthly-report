# Collecting the data

Every query below has been verified against a live store. Replace `START` and
`END` with the period's dates in `YYYY-MM-DD` form.

## Rate limiting

The analytics API refuses bursts. Run **at most two queries in parallel**, then
wait for the responses before the next group. An "Analytics API error: Rate
limited" is not fatal: wait a few seconds and re-run that query on its own.

The groups below are already cut with this in mind.

## Comparisons

`COMPARE TO previous_period` and `COMPARE TO previous_year` both work, but
**one comparison per query**. To get both, run the query twice. Comparison
columns come back prefixed `comparison_<metric>__previous_period`.

`previous_period` means the immediately preceding window of the same length,
not the previous calendar month. On a full month the two almost always
coincide; check it when the period is arbitrary.

## Group 1 — summary and sales breakdown

```
FROM sales SHOW orders, total_sales, average_order_value, gross_sales, discounts,
  sales_reversals, net_sales, shipping_charges, taxes
SINCE START UNTIL END COMPARE TO previous_period
```

```
FROM sales SHOW orders, total_sales, average_order_value
SINCE START UNTIL END COMPARE TO previous_year
```

Shopify's definitions, to carry over verbatim into the methodology:

- `gross_sales`: before discounts and returns.
- `discounts` and `sales_reversals`: **returned as negatives**. Leave them as
  they are in report.json; the script handles the sign.
- `net_sales` = gross_sales + discounts + sales_reversals.
- `total_sales` = net_sales + shipping_charges + taxes.

## Group 2 — traffic, funnel and trend

```
FROM sessions SHOW sessions, sessions_with_cart_additions,
  sessions_that_reached_checkout, sessions_that_completed_checkout, conversion_rate
SINCE START UNTIL END COMPARE TO previous_period
```

```
FROM sales SHOW total_sales TIMESERIES day SINCE START UNTIL END
COMPARE TO previous_period
```

Past 62 days, swap `TIMESERIES day` for `TIMESERIES week`.

`conversion_rate` is a fraction (0.0109 = 1.09%). Keep it as a fraction.

Daily revenue can be **negative** on a day where refunds exceed sales. That is
normal; do not correct it.

## Group 3 — customers and margin

```
FROM sales SHOW new_customers, returning_customers, customers, returning_customer_rate
SINCE START UNTIL END
```

```
FROM sales SHOW gross_profit, cost_of_goods_sold, net_sales
SINCE START UNTIL END
```

Margin only exists if cost per item is filled in on Shopify. If
`cost_of_goods_sold` is 0 while there are sales, **do not produce the margin
section**: a 100% margin rate is an artefact, not a result. Where only part of
the catalogue has costs, fill `margin.incomplete` with a sentence saying so.

## Group 4 — sources and products

```
FROM sales SHOW orders, total_sales GROUP BY order_referrer_source
ORDER BY total_sales DESC LIMIT 8 SINCE START UNTIL END
```

```
FROM sales SHOW gross_sales, orders GROUP BY product_title
ORDER BY gross_sales DESC LIMIT 10 SINCE START UNTIL END
```

For a campaign-level breakdown, group by
`order_referrer_source, order_referrer_name` instead.

Source labels, to translate into the report's language every time:

| API value | Meaning |
|---|---|
| empty string | Direct or unidentified |
| `search` | Search |
| `social` | Social |
| `email` | Email |
| `referral` | Referring sites |
| `unknown` | Unidentified |

The empty row is almost always the largest: it holds direct traffic and every
visit whose browser sent no referrer. Say so in the methodology, or the reader
takes it for pure direct traffic.

## Group 5 — devices, countries, stock, returns

```
FROM sessions SHOW sessions, conversion_rate GROUP BY session_device_type
ORDER BY sessions DESC SINCE START UNTIL END
```

```
FROM sessions SHOW sessions GROUP BY session_country
ORDER BY sessions DESC LIMIT 6 SINCE START UNTIL END
```

```
FROM inventory SHOW ending_inventory_units, inventory_units_sold, sell_through_rate
GROUP BY product_title ORDER BY inventory_units_sold DESC LIMIT 8
SINCE START UNTIL END
```

```
FROM sales SHOW sales_reversals GROUP BY product_title
ORDER BY sales_reversals ASC LIMIT 6 SINCE START UNTIL END
```

Sorting `sales_reversals` ascending does surface the largest returns, since the
values are negative. Pass absolute amounts into report.json.

Translate device types and country names into the report's language.

## Group 6 — how sales break down

These four queries carry most of what separates a readable report from a data
dump.

```
FROM sales SHOW orders, total_sales GROUP BY sales_channel
ORDER BY total_sales DESC LIMIT 10 SINCE START UNTIL END
```

```
FROM sales SHOW gross_sales, orders GROUP BY product_type
ORDER BY gross_sales DESC LIMIT 8 SINCE START UNTIL END
```

```
FROM sales SHOW gross_sales GROUP BY product_variant_title
ORDER BY gross_sales DESC LIMIT 12 SINCE START UNTIL END
```

```
FROM sales SHOW orders, total_sales GROUP BY billing_country
ORDER BY total_sales DESC LIMIT 8 SINCE START UNTIL END
```

Channel names to translate: `Online Store`, `Draft Orders`, `Point of Sale`,
`Shop`. Any other channel is a marketplace or an app; keep its name as is.

**Mark the online store channel with `"online": true`** in report.json. Without
that marker the salience engine cannot tell online sales from the rest, since
the label has been translated.

`product_type` returns one row with an empty label, holding products with no
type set: drop it before writing report.json.

## Group 7 — monthly history

```
FROM sales SHOW total_sales, orders TIMESERIES month SINCE -24m UNTIL today
```

```
FROM sales SHOW gross_sales, sales_reversals TIMESERIES month SINCE -12m UNTIL today
```

```
FROM sessions SHOW sessions, conversion_rate TIMESERIES month SINCE -12m UNTIL today
```

The first feeds available history, the "month in context" chapter, and
seasonality detection. The other two are the reference the 90-day plan sets its
targets against: without them, no workstream can name a goal.

Format month labels short and in the report's language ("Aug 26"), otherwise
the chart axis becomes unreadable.

## Branding

### Colours

Read the published theme's settings file:

```graphql
query {
  themes(first: 1, roles: [MAIN]) {
    nodes {
      id
      name
      files(filenames: ["config/settings_data.json"], first: 1) {
        nodes {
          body { ... on OnlineStoreThemeFileBodyText { content } }
        }
      }
    }
  }
}
```

Save the `content` field **exactly as it comes** and pass it with `--theme`. Do
not try to pull the colours out by hand: the script handles the three families
of themes (colour schemes on modern OS 2.0 themes, flat keys on premium themes,
frequency detection when nothing is recognised) and fixes contrast.

If the query fails for lack of theme permission, carry on without `--theme`.

### Logo

Look in `settings_data.json` for a `logo`, `header_logo`, `favicon` or similar
key. Its value looks like `shopify://shop_images/my-logo.png`. Resolve the
filename to a URL:

```graphql
query {
  files(first: 5, query: "filename:my-logo.png") {
    nodes { ... on MediaImage { image { url width height } } }
  }
}
```

Download it as PNG and pass it with `--logo`. The script drops a light chip
behind a logo too dark for the cover, so a monochrome logo is not a problem.

With no logo, force nothing: the cover stands on its own.

## Consistency checks

Run these before writing report.json. Each one comes from a real mismatch.

- `orders` from group 1 and `sessions_that_completed_checkout` from group 2
  **often differ**, sometimes twofold. Sessions cover the online store only;
  orders cover every channel. Group 6 quantifies the gap precisely: on one real
  store, 210 orders split into 175 online store, 21 marketplace and 14 manual
  orders, against 101 sessions that completed a checkout. Do not correct it:
  give the channel breakdown in `methodology`, because it is the first question
  a merchant asks of their report.
- Total sales by source can come in under the overall total: some orders carry
  no source.
- The top 10 products total less than gross sales as soon as the catalogue is
  larger. Never present that subtotal as a total.
- `returning_customer_rate` covers customers in the period, not the whole
  customer base.
