# Examples

`report.example.json` is a complete, runnable report for a fictional store,
Marlow Goods. Every figure in it is made up. It doubles as the reference
implementation of the data contract described in
[`report-schema.md`](../skills/shopify-monthly-report/references/report-schema.md).

```bash
cd ../skills/shopify-monthly-report/scripts
python3 build_report.py --data ../../../examples/report.example.json \
  --lang en -o report.pptx
```

Swap `--lang en` for `--lang fr` to see the French edition, including the
change in number and currency formatting.

`settings_data.example.json` is a minimal theme settings file. Pass it with
`--theme ../../../examples/settings_data.example.json` to see the deck in the
store's colours instead of the neutral fallback palette.

The example also carries a `previous_plan`, so the deck opens on the follow-up
slide that measures the targets last month's plan set.

The client configuration template lives at
[`skills/shopify-monthly-report/assets/config.example.json`](../skills/shopify-monthly-report/assets/config.example.json).
