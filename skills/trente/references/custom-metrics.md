# Permanent metrics

A permanent metric is a view the merchant asked for once and finds in every
report after that: a map of orders by department, the number of customers with
a tag, the share of orders placed with a discount code, the sales of one
collection.

What is stored is the **recipe**: the queries to run, the view to draw and the
columns to read. The figures are not stored, except the last value of a stock
metric (see `last`). Recipes live in the context metafield under
`custom_metrics`, and each report runs them again on its own period.

## Rules

- **Only on an explicit request.** Never add a metric because it would be
  interesting. Never add one without the merchant's confirmation.
- **At most 8.** Past that, ask which one to remove first.
- **They are shown, never judged.** A permanent metric does not feed the
  highlights or the plan, and its slide follows `writing-rules.md`: no cause,
  no means, no judgement. The title says what is measured, nothing more.
- **No personal data.** Queries return counts and sums. Never a name, an email
  or an address. A postcode only ever comes grouped, as a dimension of a
  ShopifyQL query.
- **A failed query never becomes an estimate.** The slide is left out with a
  warning, and the recipe stays.

## Adding a metric

1. **Say back what will be measured**, in one sentence, with what it will be
   compared to: "Each month, the number of customers tagged `abonné`, compared
   with the previous report." Ask for any parameter that is missing: the
   exact tag, the codes, the collection's name as it appears in Shopify.
2. **Check that the parameter exists.** A tag: `customersCount` returns more
   than zero. A collection: it shows up in `search_collections`. A code: it
   appears in the `discount_code` breakdown. A recipe built on a misspelt tag
   returns zero every month, and nobody notices.
3. **Choose the view**:

   | View | For |
   |---|---|
   | `kpi` | One figure, with up to three secondary figures beside it |
   | `bars` | A ranking by a dimension: codes, collections, cities |
   | `table` | The same ranking, when the labels are long or the values many |
   | `map_fr` | A figure by French department, read from shipping postcodes |
   | `map_world` | A figure by country, read from shipping country codes |

4. **Write the queries**, starting from the recipes below when one fits. A
   `flow` query (anything measured over the period) reads the period through
   `SINCE START UNTIL END` and adds `COMPARE TO previous_period`.
5. **Run them on this report's period** and check the answer: rows present,
   values plausible, the parameter matched. Copy the rows into report.json
   (see "Rows").
6. **Build the deck.** The slide appears in the "Your metrics" chapter, after
   the others.
7. **Ask before saving**: "Shall I add it to every report from now on?" On a
   yes, write the recipe to a file, check it with

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/skills/trente/scripts/custom_metrics.py" --check context.json
   ```

   then append it, **without** its `data`, to `custom_metrics` in the context,
   which is written to the metafield at step 10.

## Every month

For each recipe in `custom_metrics`:

1. Run each query **verbatim**, replacing `START` and `END` with the period's
   dates. They count in the two-queries-at-a-time limit like the others.
2. Copy the recipe into report.json under `custom_metrics`, and add the rows
   under `data`, one key per query name.
3. Never rewrite a query to make it pass. If it fails, leave its `data` out:
   the builder skips the slide with a warning. Name the failure in the
   delivery summary. If a recipe fails two months running, ask the merchant
   whether to fix it or remove it.

After the build, the script prints `custom_metrics_last`: for every `stock`
metric, the value just measured. Write it to that recipe's `last` before
storing the context, or next month's slide has nothing to compare with.

## Listing, changing, removing

"What are my permanent metrics?": list each one's title and the date it was
added. "Remove the map": take it out of `custom_metrics` and write the
context. To change a parameter, edit the recipe, run it on the current period
to check it, and keep the same `id` so its `last` value carries over.

## The recipe

```json
{
  "id": "subscribers",
  "title": "Clients tagués abonné",
  "request": "le nombre de clients avec le tag abonné",
  "added": "14 octobre 2026",
  "view": "kpi",
  "kind": "stock",
  "unit": "number",
  "source": "Shopify, clients tagués abonné",
  "queries": [{"name": "count", "tool": "graphql_query", "query": "..."}],
  "value": {"query": "count", "field": "count"},
  "details": [],
  "last": {"period": "2026-09", "label": "Septembre 2026", "value": 118}
}
```

| Field | |
|---|---|
| `id` | Lowercase letters, digits and hyphens. Stable: it carries `last` over. |
| `title` | The slide title, in the report's language. |
| `request` | The merchant's words, kept to tell what was asked. |
| `added` | The date it was added, written out in the report's language. |
| `view` | `kpi`, `bars`, `table`, `map_fr` or `map_world`. |
| `kind` | `flow` for a quantity over the period (orders, sales, a share); `stock` for a count at a date (customers with a tag). A stock compares with `last`. |
| `unit` | `number`, `money` or `percent`. A ratio is always a percent. |
| `source` | One line for the caption: where the figure comes from. |
| `queries` | `name`, `tool` (`run-analytics-query` or `graphql_query`) and `query`. |
| `last` | Stock metrics only: written from `custom_metrics_last`. |

What the view reads:

- **`kpi`**: `value` is `{query, field}`, the sum of a column over the rows,
  or `{num: {...}, den: {...}}` for a ratio. Add `compare_field` to read the
  comparison column. `details` holds up to three `{label, unit, value}`.
- **`bars` and `table`**: `rows` is `{query, label, field}`, with
  `compare_field`, `label_title` (the column header) and `limit` (10 by
  default) optional. Rows are sorted by value, largest first.
- **`map_fr`**: `map` is `{query, postal, country, field}`, with
  `compare_field`, `measure` (what is counted, as the legend names it) and
  `per_capita` (true by default) optional.
- **`map_world`**: `map` is `{query, country, field}`, with `compare_field`,
  `measure` and `per_capita` (false by default: the value as is) optional.

## Rows

`data` holds, for each query name, the rows exactly as the tool returned them:

- **`run-analytics-query`**: a list of objects keyed by column name. If the
  answer comes as columns plus rows of values, zip them into objects. Keep the
  numbers as numbers.
- **`graphql_query`**: the object holding the fields, in a list. For
  `customersCount`, `[{"count": 131, "precision": "EXACT"}]`. A precision
  other than `EXACT` means a lower bound, and the slide says "or more".

## Recipes

The queries below follow the ShopifyQL and Admin API references. They have not
all been run against a live store yet: check the first answer before saving a
recipe built on one.

### Customers with a tag

A `stock` `kpi`. The count comes from the Admin API; the orders and sales of
those customers over the period come from ShopifyQL.

```graphql
query { customersCount(query: "tag:'abonné'") { count precision } }
```

Several tags: `tag:'abonné' OR tag:'vip'`. A tag holding a space or a quote
stays inside the single quotes.

```
FROM sales SHOW orders, total_sales WHERE customer_tags CONTAINS 'abonné'
SINCE START UNTIL END COMPARE TO previous_period
```

Recipe: `value` `{query: "count", field: "count"}`; `details` on `orders` and
`total_sales`, with `compare_field` `comparison_orders__previous_period` and
`comparison_total_sales__previous_period`.

### Share of orders with a discount code

A `flow` `kpi`, as a ratio of two queries.

```
FROM sales SHOW orders SINCE START UNTIL END COMPARE TO previous_period
```

```
FROM sales SHOW orders WHERE discount_code IS NOT NULL
SINCE START UNTIL END COMPARE TO previous_period
```

For given codes only: `WHERE discount_code IN ('BIENVENUE10', 'ETE15')`.
Recipe: `value` `{num: {query: "coded", ...}, den: {query: "all", ...}}`.

### Orders by discount code

A `flow` `bars`.

```
FROM sales SHOW orders WHERE discount_code IS NOT NULL GROUP BY discount_code
ORDER BY orders DESC LIMIT 10 SINCE START UNTIL END COMPARE TO previous_period
```

An order carrying two codes counts once under each.

### Sales of a collection

A `flow` `kpi`, with the collection's share of total sales as a detail.

```
FROM sales SHOW total_sales, orders WHERE product_collection = 'Voyage'
SINCE START UNTIL END COMPARE TO previous_period
```

```
FROM sales SHOW total_sales SINCE START UNTIL END COMPARE TO previous_period
```

`orders` counts the orders holding at least one product of the collection.

### Orders by department

A `flow` `map_fr`.

```
FROM sales SHOW orders, total_sales
WHERE shipping_country_code IN ('FR', 'GP', 'MQ', 'GF', 'RE', 'YT')
GROUP BY shipping_country_code, shipping_postal_code
SINCE START UNTIL END COMPARE TO previous_period
```

Shopify gives the overseas departments their own country codes, hence the
list. Recipe: `map` `{query: "orders", postal: "shipping_postal_code",
country: "shipping_country_code", field: "orders", compare_field:
"comparison_orders__previous_period", measure: "Commandes"}`. For sales per
inhabitant, read `total_sales` and set `unit` to `money`.

How the builder reads it:

- The department is the postcode's first two digits. Corsica is split at
  20200: below is Corse-du-Sud (2A), from it Haute-Corse (2B). Overseas
  departments read three digits (971 to 976).
- Monaco (98000), Saint-Barthélemy (97133), Saint-Martin (97150), the other
  overseas collectivities and malformed postcodes are counted apart, and the
  caption gives their total.
- The rate is per 100,000 inhabitants, from the INSEE reference populations
  bundled with the plugin (`assets/fr-departments.json`, year in the
  caption). Mayotte has no reference population: it is drawn, marked as
  having none, and left out of the ranking.
- The map shows metropolitan France, an Île-de-France inset and the five
  overseas departments. Shades are quantiles, so every one is in use. The
  right-hand panel gives the national rate and the ten departments with the
  highest rate.

### Orders by country

A `flow` `map_world`.

```
FROM sales SHOW orders GROUP BY shipping_country_code
SINCE START UNTIL END COMPARE TO previous_period
```

Recipe: `map` `{query: "countries", country: "shipping_country_code", field:
"orders", compare_field: "comparison_orders__previous_period", measure:
"Commandes"}`.

How the builder reads it:

- The map shows the number of orders as it is, by default. With
  `per_capita: true` it shows orders per million inhabitants, from the World
  Bank populations bundled with the plugin (`assets/world-countries.json`).
- Shopify gives the overseas departments their own country codes (GP, MQ, GF,
  RE, YT). The world map draws them as part of France, and the caption says
  so. A code the map does not have is counted apart.
- The world is drawn in the Equal Earth projection, which keeps areas true,
  without Antarctica. A Europe inset, drawn larger, keeps Belgium,
  Switzerland, Luxembourg or Malta visible. The right-hand panel gives the
  total, the number of countries and the ten countries with the most orders.
