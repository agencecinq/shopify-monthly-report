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

The client configuration template lives at
[`skills/shopify-monthly-report/assets/config.example.json`](../skills/shopify-monthly-report/assets/config.example.json).
