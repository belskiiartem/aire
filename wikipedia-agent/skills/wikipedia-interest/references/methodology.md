# Methodology

## Data
- **Source**: Wikimedia Analytics API – `pageviews/per-article` (topic articles) and `pageviews/aggregate` (whole edition), monthly, `all-access`, `agent=user`.
- **Complete months only**. The end month defaults to the last complete month. Requests always end on the *last day* of the end month: the per-article endpoint truncates a monthly bucket at the end day, so ending on the 1st returns one day labelled as a whole month.
- **Article matching**: seed title in the source edition (redirects followed) → Wikidata interlanguage links → the title in each target edition. Keyword search is used only to produce *unverified candidates*. It is never used automatically, because cross-language keyword search often returns unrelated pages (e.g. `pl` search for "Intermittent fasting" returns "Stres oksydacyjny").
- **Clusters**: several seeds are summed per edition. If some seeds have no article in an edition, a `partial` warning is raised, because the cluster is then not like-for-like.
- **Cache**: SQLite (`$WIKI_INTEREST_CACHE`). Complete months are immutable, so pageviews are cached indefinitely; title lookups expire after 7 days.

## Metrics
| Metric | Definition |
|---|---|
| `growth_pct` | Σ last 12 months ÷ Σ previous 12 − 1 (falls back to `window`-month halves when < 24 months). |
| `share_growth_pct` | Same, computed on views per million edition views. It separates topic interest from overall edition traffic changes, e.g. the long-term drift from web to AI assistants. |
| `edition_growth_pct` | Same, for the edition total (context). |
| `start_vs_end_pct` | Σ last `window` months ÷ Σ first `window` months − 1. Sensitive to seasonality if the windows cover different seasons. |
| `theil_sen_pct_per_year` | Median pairwise slope × 12 ÷ median views. Robust to single spikes. |
| `trend_test` | Seasonal Mann-Kendall (≥ 24 months) or plain Mann-Kendall. Compares each calendar month only with itself, so recurring school-year or New-Year peaks are not read as growth. With exactly 24 months it reduces to counting `months_up_vs_year_before`. |
| `seasonality_strength` | Share of detrended variance explained by calendar month (0–1). |
| `spike_months` / `spike_driven` | Months > 3× median. The change counts as spike-driven if capping spikes flips its sign or halves it. |

## Confidence grade
One point each for: ≥ 24 months; p < 0.05 (half a point for p < 0.10); not spike-driven; median ≥ 1000 views/month (half a point for ≥ 300); raw and edition-adjusted growth agree in sign.
**High** ≥ 4, **medium** ≥ 2.5, otherwise **low**. A median below 300 views/month caps the grade at medium. Every missed point adds a human-readable entry to `confidence_reasons`.

## Known limitations
- Views arriving via redirects to the article are not counted (only the exact title).
- Language edition ≠ country. English, Spanish, Russian, Arabic and similar editions serve many countries.
- Some automated traffic is not identified by Wikimedia and remains in `user`.
- Pageview interest ≠ purchase intent. Treat results as a filter for further research.
- The edition-adjusted metric assumes the edition's total traffic is a fair baseline for its audience size.
