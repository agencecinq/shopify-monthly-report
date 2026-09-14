# Store context

Profiling works out what the API can say. The context collects what it cannot:
where the merchant wants to go, what they consider acceptable, what they know
about the reliability of their own data, and who will read the report.

This is what lets the plan set fair targets without inventing an industry
benchmark.

## Where it lives

In a metafield on the store itself, which makes it portable: it follows the
merchant if they change machine, and next month's report finds it again with no
file to keep.

```
namespace : shopify_report
key       : context
type      : json
owner     : the Shop
```

Reading:

```graphql
query { shop { id name myshopifyDomain
  metafield(namespace: "shopify_report", key: "context") { value updatedAt } } }
```

Writing:

```graphql
mutation SetCtx($m: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $m) {
    metafields { id } userErrors { field message code }
  }
}
```

with `ownerId` set to the Shop id, `type` to `json`, and `value` the context as
a JSON string.

If the write fails for lack of permission, do not push: offer to keep the
context in a `context-<domain>.json` file the merchant holds, and ask for it
again next month. Never block the report over it.

## Never invent an answer

A context field is filled only by an explicit answer from the user. Never by
deduction, never with a plausible value, never "just to test".

The reason is simple: once written to the metafield, a declared revenue target
or return threshold is indistinguishable from a real answer. It will drive the
plan's targets for months, and nobody will know it was assumed.

An unanswered field stays `null`, and its question comes back next month. A
half-empty context is normal and harmless: the report is produced anyway, it
simply sets its targets from the store's internal reference.

The same rule covers the write itself: do not write to a production store's
metafield to try the mechanism out. Test on a development store.

## Making it visible in the admin

A metafield created through the API **does not appear** in the Shopify admin
until a definition declares it. It exists, the API reads and writes it, but the
merchant sees it nowhere and can correct nothing.

On first install for a store, create the definition just before writing the
context:

```graphql
mutation Def($d: MetafieldDefinitionInput!) {
  metafieldDefinitionCreate(definition: $d) {
    createdDefinition { id access { admin storefront } }
    userErrors { field message code }
  }
}
```

```json
{"d": {"name": "Monthly report context",
       "namespace": "shopify_report", "key": "context",
       "description": "Context used by the monthly report: declared targets, thresholds, data reliability and the 90-day plan in progress.",
       "type": "json", "ownerType": "SHOP"}}
```

**Do not pass an `access` block.** The schema only accepts `MERCHANT_READ` and
`MERCHANT_READ_WRITE` for `access.admin`, while the server demands
`public_read_write` for this namespace: both schema-valid values are rejected
and the mutation fails. With no `access` block, Shopify applies
`PUBLIC_READ_WRITE` in admin and `NONE` in storefront, which is exactly what is
wanted: the merchant can read and correct their context from Settings,
Metafields and metaobjects, Shop, and nothing is exposed on the public store.

An existing definition returns a `TAKEN` error: that is expected, pass over it
and carry on. The existing metafield attaches itself to the definition.

## Spotting a new store

On start, after `get-shop-info`, read the metafield.

- **Absent or unreadable**: first time on this store. Create the definition and
  run the opening questionnaire before producing anything.
- **Present**: take up the context, confirm in one sentence what is on file, and
  ask the month's enrichment question (below).

Always check the context's `myshopifyDomain` against the connected store. A
context that does not match belongs to another store: ignore it and start from
the questionnaire.

## The opening questionnaire

Six questions, not one more. A merchant made to answer fifteen questions before
their first report will never ask for a second.

Ask them **one at a time**, confirming each answer briefly. Accept a missing
answer: the field stays empty and the question comes back later.

1. **Who will read this report?** You alone, your partners, or a board and
   investors. Sets the level of explanation and the tone.
2. **What do you sell, and to whom?** One sentence is enough. Feeds the
   customers chapter note and checks the profile drawn from the API.
3. **Do you have a revenue target for the year?** An amount, or nothing. Adds a
   progress marker to the report.
4. **Is cost of goods filled in on Shopify?** All, some, or none. Decides
   whether the profitability chapter is published: a margin computed on a
   half-filled catalogue is wrong, and wrong in the flattering direction.
5. **What return rate do you consider acceptable?** Becomes the target of the
   refunds workstream, in place of the internal convention.
6. **Any channels to leave out of the report?** Marketplace, manual orders,
   point of sale. Some merchants do not want them mixed in.

## Monthly enrichment

From the second report on, ask **one** question, picked from those still
unanswered, and record it. The context fills out over the months without ever
weighing on the merchant.

Reserve of questions, in order:

- Which months are usually your strongest?
- Anything planned next month, sales or launches?
- What is your monthly advertising budget?
- What margin rate are you aiming for?
- Do you use a returns or reviews app?

Record answered questions in `questions_asked`, including those the merchant
declined to answer, so they are not asked again.

## Context structure

```json
{
  "version": 2,
  "shop": "marlow-goods.myshopify.com",
  "created_at": "2026-09-14",
  "updated_at": "2026-09-14",
  "audience": "founder",
  "activity": "Leather bags and small goods, sold direct in the UK and Ireland.",
  "annual_revenue_target": 420000,
  "cost_of_goods": "partial",
  "acceptable_return_rate": 0.12,
  "excluded_channels": [],
  "expected_seasonality": null,
  "monthly_ad_budget": null,
  "target_margin_rate": null,
  "questions_asked": ["audience", "activity", "annual_revenue_target",
                      "cost_of_goods", "acceptable_return_rate",
                      "excluded_channels"],
  "previous_plan": {
    "period": "August 2026",
    "workstreams": [{"key": "returns", "title": "Refunds", "unit": "rate",
                     "current": 0.1704, "target": 0.119,
                     "milestones": [0.153, 0.136, 0.119], "monthly_gain": 1955}]
  }
}
```

`previous_plan` is written by the script on every report, through the `--state`
option. It is what feeds the next month's follow-up slide: without it, the plan
is only an intention nobody ever verifies.

## What the context changes

| Field | Effect on the report |
|---|---|
| `audience` | A board or an investor gets more explicit reading lines and a full methodology. A founder alone can do without. |
| `activity` | Feeds `customers.note` and checks the profile drawn from the API. |
| `annual_revenue_target` | Adds year-to-date progress through `ytd`. |
| `cost_of_goods` = `none` | The profitability chapter is not published. |
| `cost_of_goods` = `partial` | The chapter is published with `margin.incomplete` filled in. |
| `acceptable_return_rate` | Becomes the refunds workstream target when it is within reach over 90 days. |
| `excluded_channels` | The named channels drop out of the channels chapter and the totals, and the methodology says so. |
| `previous_plan` | Feeds the follow-up slide. |

Carry these fields into `report.json` under `context`.

## Several stores

The Shopify connector talks to one store at a time. To switch, call
`switch-shop`, then immediately `get-shop-info`: without that confirming call
the switch stays incomplete.

Each store carries its own context in its own metafield. There is nothing to
manage on the file side, and no way to mix two clients up.

When the user asks for a report on a store that is not the connected one:

1. Announce the switch and call `switch-shop`.
2. Call `get-shop-info` and check it is the right store.
3. Read that store's context metafield.
4. Run the report as usual.

Warn that switching revokes access to the previous store and that a new
authorisation will be asked for to go back. On a request covering several
stores, handle one store at a time, confirming each switch, and deliver one
file per store. Never merge two stores' figures into one report: currencies,
time zones and channel scopes differ.
