# Chart preview

Serve `docs` with `python -m http.server 8765 --directory docs` and open
http://localhost:8765. The three chart views, Rankings, and Detailed results share metrics and
vendor/year filters. Bar charts and F1 axes are linear with a zero baseline.
Charts default to All models; Top 10/15/20 remain optional shorter views.
Performance is the default tab. Both tables retain every column and use vendor
logos plus separate OpenRouter and shot-count badges, without rank medals.
Reloads return to Performance even with an old table URL fragment; fresh table
deep links still work. Detailed F1 cells retain green (≥0.8), amber (≥0.5), and
red (<0.5) indicators for models, files, and runs.

- Performance: F1, precision, recall; F1 intervals use the existing bootstrap.
- Token price: paired input and output rates, from `pricing.json`.
- Rankings: the original sortable leaderboard, with all matching models and
  expandable testing notes. It is no longer repeated beneath the charts.
- Detailed results: the expandable model/file/run table, preserving drill-down
  state when switching views. Neither table is repeated below the tabbed explorer.
- Value: F1 against an illustrative workload price. Output volume and a price
  ceiling are adjustable. Cost uses a logarithmic axis with dollar tick labels;
  free models use a separate $0 column. The frontier is recomputed from the
  original prices and F1 scores among displayed models.

Refresh prices with `python scripts/build_site_pricing.py`. Exact OpenRouter IDs
are matched against the public catalog; direct API prices require verified
entries in `config/model_pricing_overrides.json`. Missing prices stay missing.

New predictions include `inference.usage`, with raw provider usage plus normalized
input, output, cache, image, reasoning, answer, and cost fields. Unreported fields
are null. Input/cache/image and output/reasoning fields overlap; do not sum them.
An append-only `predictions/eval/usage/*_prediction.jsonl` audit retains API failures,
parse failures, and manual retries. API errors with no returned usage have unknown
cost. These costs cover candidate inference, not the separate evaluation judge.
The site builder joins usage only for matching evaluated prediction filenames.

Run `python scripts/build_site_seo.py` after editing results or prices. It generates
the initial HTML ranking snapshot, standalone `/rankings.html`, Markdown views,
`llms.txt`, `robots.txt`, sitemap, and metadata. `--check` detects stale output.
The Pages workflow regenerates these before every deployment. It deploys committed
code from `main`; no release-upload preview mechanism is needed.

The interactive explorer replaces the static snapshot only after successful
initialization. With JavaScript disabled or unavailable, the static results remain
readable. The standalone rankings page is always available from the footer.
No model metrics are invented; the generator mirrors the client aggregation and
browser checks compare every model. Confidence intervals remain in the interactive
view. Unknown prices remain unknown. Sitemap dates are omitted rather than guessed.

After deployment, an account owner should submit the sitemap in Google Search
Console and Bing Webmaster Tools and use URL Inspection to verify indexing.
The site files alone cannot confirm search-engine indexing or account ownership.
