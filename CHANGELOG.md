# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[semantic versioning](https://semver.org/).

## [Unreleased]

### Fixed

- The plan no longer labels a target "three tenths better than today" when the
  ceiling does not bind: an old best month within reach is shown as the best
  month. The conversion finding quotes the best month, not the target.
- Orders with no identified referrer are no longer treated as a traffic source.
  They are left out of the dependency workstream and finding, which now read
  shares of attributed revenue as they always said they did. Rows are marked
  `"unattributed": true` in report.json.
- A store whose refund rate is at or under the threshold it declared gets no
  refunds workstream, instead of being pushed below it.
- The follow-up slide measures dependency and concentration workstreams, and
  keeps a line marked n/a for any workstream it cannot measure, instead of
  dropping it.
- Monthly histories are queried up to the period's end, not `today`, and carry
  `month` as `YYYY-MM`. The builder drops months after the period and warns
  when a series ends early.
- Rule and plan errors are reported in a `warnings` list and on stderr instead
  of silently removing a finding or a slide. A follow-up error no longer empties
  the plan while its state is still written to the metafield.
- The worked example's history now agrees with its own KPIs.
- `writing-rules.md` no longer uses the em dashes it forbids.

### Added

- Permanent metrics. A merchant can ask for a view once and find it in every
  report: a `kpi`, `bars`, `table` or `map_fr` view over queries stored as a
  recipe in `context.custom_metrics`. They are drawn in a "Your metrics"
  chapter and never feed the highlights or the plan. A stock metric, such as
  customers with a tag, compares with the value stored at the last report.
  See `references/custom-metrics.md`.
- A map of France by department, with Île-de-France and the five overseas
  departments as insets, and rates per 100,000 inhabitants from the INSEE
  reference populations. The outlines (IGN Admin Express, Licence Ouverte) and
  populations are bundled in `assets/fr-departments.json`, rebuilt with
  `tools/build_fr_map.py`.
- A closing slide on Trente and CINQ: where the data goes, and a link to reach
  CINQ.
- SKILL.md checks python-pptx before collecting any data, and stops with one
  sentence when the environment cannot install it. The builder exits with an
  install hint instead of a traceback, and warns when the logo is left out for
  lack of Pillow instead of dropping it silently. The READMEs state python-pptx
  as a hard dependency and Pillow as optional.
- Test suite (`tests/`) and a CI workflow running it, the structure check and
  the example build in both languages.
- `examples/settings_data.example.json` and a `previous_plan` in the example,
  so it shows the themed deck and the follow-up slide.

### Changed

- The plugin is now called Trente. It installs as `trente@agencecinq`, and the
  skill lives in `skills/trente`. Reinstall it under the new name; the context
  and plan stored in the shop metafield `shopify_report.context` are kept.
- The cover says the deck was generated with Trente.
- **The plan is now monthly.** Each workstream sets one target for next month,
  and next month's report measures that same target. The 90-day horizon and
  its three milestones are gone: only the first milestone was ever measured,
  and the plan was rewritten every month anyway. Plans stored in the old format
  still feed the follow-up, through their first milestone.
- One-month ambition: an old, out-of-reach best month is capped at a one-tenth
  improvement (was three tenths over 90 days), dependency shares move by two
  points (was five), the no-history refunds convention is a one-tenth
  reduction (was one fifth), and the gain threshold is 1% of revenue (was 2%,
  measured on a gap three times larger).
- A level reached in the last two months is the target when it beats a capped
  old best month, and no refunds target goes below the merchant's declared
  threshold.
- The plan slide shows each target's reference instead of the milestones.
- The READMEs describe how targets are actually set, and call the refunds gain
  sales kept rather than money recovered.

## [1.0.1] - 2026-09-16

### Fixed

- Added `.claude-plugin/marketplace.json`, without which the repository is not
  an installable plugin source: `/plugin marketplace add` rejected it and only
  `plugin.json` was present. Installation now works from the GitHub repository.

### Changed

- Install instructions in both READMEs give the two commands that actually
  install the plugin, instead of pointing at a Releases page.
- `tools/validate_plugin.py` fails when `marketplace.json` is missing, lists no
  plugin, or disagrees with `plugin.json` on the name or version.

## [1.0.0] - 2026-09-14

First public release.

### Added

- Monthly Shopify report as a PowerPoint deck, in the store's theme colours.
- Store profiling: catalogue structure, sales model, purchase cycle and
  seasonality decide which chapters appear and in what order.
- Salience engine computing measured findings from numeric rules.
- 90-day plan with targets drawn from the store's own history, monthly
  milestones and a calculated gain per workstream.
- Follow-up slide measuring the previous month's milestones.
- Context and plan stored in a Shopify shop metafield, with a metafield
  definition so the merchant can read and correct them from the admin.
- Six-question opening questionnaire, then one enrichment question per month.
- Multi-store support through `switch-shop`, one context per store.
- English and French, including number and currency conventions per language.
- Complete worked example on a fictional store, runnable without Shopify.
