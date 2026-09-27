---
name: wikipedia-interest
description: Measure and compare public interest in topics across Wikipedia language editions using Wikimedia pageview data. Produces trend metrics with a confidence grade, charts and a one-page PDF report. Use when someone asks whether interest in a topic is growing, which languages/markets to explore next, or wants a shareable report on topic interest by language.
compatibility: Python 3.10+, network access to wikimedia.org and *.wikipedia.org. Install with `pip install -r requirements.txt`.
metadata:
  version: "0.2.0"
---

# Wikipedia interest

All data work is done by `scripts/wiki-interest`. **Do not write your own code** for fetching or statistics – run the commands below from this skill's directory and interpret their JSON.

## 1. Translate the request into one `analyze` call

| Need | Flag | Default |
|---|---|---|
| Topic name for titles | `--topic "Astronomy"` | required |
| Wikipedia editions | `--languages uk,pl,cs` (ISO codes, max 12) | required |
| Article(s) that represent the topic | `--seed "Astronomy"` (English title; repeat for a cluster) | = `--topic` |
| Time range | `--period 2y` / `18m`, or `--start 2023-01 --end 2025-12` | 2y to last complete month |
| Start-vs-end window | `--window 6` | 6 |
| Seeds in another language | `--source-lang uk` | en |
| Force a title | `--article pl="Post przerywany"` (repeatable) | – |

Seeds are **English Wikipedia titles** (the skill follows Wikidata links to every other language). Translate the user's topic to the English article title yourself: "інтервальне голодування" → `--seed "Intermittent fasting"`.
For broad topics use 2–4 seeds, e.g. learning English → `--seed "English language" --seed "English as a second or foreign language"`.

```bash
python scripts/wiki-interest analyze --topic "Intermittent fasting" --seed "Intermittent fasting" --languages pl,cs --period 2y
```

One call fetches all languages, writes `chart.png`, `report.pdf`, `observations.csv`, `analysis.json` and prints a compact JSON summary. **Run it once per question; never repeat an identical command.** Repeated data comes from a local cache.
Language codes are Wikipedia edition codes: uk (not ua), cs (not cz), vi (not vn), ja, ko, el, sv, da, zh, he.

## 2. Check the output before answering

- `missing_languages` / `unresolved`: no equivalent article exists in that language. Say so. **Never** treat `unverified_candidates` as the topic unless the user confirms one; then re-run with `--article LANG=Title`.
- `warnings`: repeat them to the user if they change the conclusion. `only 1/2 seed articles exist` means the languages are not like-for-like; either re-run with seeds that exist everywhere or state it.
- `error`: report it; do not invent numbers.

## 3. Interpret with these rules

| Field | Meaning |
|---|---|
| `direction` | `rising` / `falling` = change > 5 % **and** trend test p < 0.10; else `no clear trend` |
| `growth_pct` | last 12 months vs previous 12 (see `growth_basis`) |
| `share_growth_pct` | same, but for the article's share of all views in that edition. **Use this to compare languages** – it removes edition-wide traffic changes |
| `months_up_vs_year_before` | e.g. `9/12` – plain-language consistency of the trend |
| `trend_p` | seasonal Mann-Kendall p-value (lower = more consistent) |
| `spike_months` | months > 3× median (news, viral events) |
| `confidence` + `confidence_reasons` | high / medium / low and **why** – always quote the reasons |

- Compare trends and `share_growth_pct` across languages, **never raw view totals** (editions differ in size).
- `ranking` is sorted by `share_growth_pct`; call it that, not "best market".
- Pageviews show reading interest, not willingness to pay. Recommend what to *investigate next*, not what to *build*.
- The trend is weak if confidence is low, if `growth_pct` and `share_growth_pct` have different signs, or if it depends on `spike_months`.

## 4. Answer format (keep it short)

1. **Answer** in 1–2 sentences, with the key number and confidence.
2. **Evidence**: a small table per language (median views/month, growth, edition-adjusted growth, months up, confidence).
3. **Caveats**: missing languages, reasons for reduced confidence, the pageviews ≠ demand caveat.
4. **Next steps**: 2–3 concrete checks (e.g. search-volume data, surveys, a landing-page test in the leading language).
5. Links/paths to `report.pdf` and `chart.png` from `artifacts`.

## 5. Reports

If the user asks for a report, summary document or something to share, **always** finish by re-rendering the PDF with your own conclusions and next steps (the first PDF only has auto-generated text), then give the link:

```bash
python scripts/wiki-interest report --run <run_id> --summary "..." --finding "..." --finding "..." --next-step "..."
```

## 6. Follow-up questions

- Questions about numbers you already have (e.g. "compare the last 6 months with the first 6" → `start_vs_end_pct`): **answer from the previous result, do not run analyze again**. For details use `python scripts/wiki-interest show --run <run_id> --language uk`; `runs` lists earlier run ids.
- A different period, extra languages or seeds: run `analyze` again with the changed flags. Cached months are not downloaded again.
- "Compare the last 6 months with the first 6": use `start_vs_end_pct` (change `--window` if needed).

Metric definitions and known limitations: [references/methodology.md](references/methodology.md).
