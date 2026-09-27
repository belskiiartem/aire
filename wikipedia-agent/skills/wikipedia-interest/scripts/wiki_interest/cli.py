"""wiki-interest CLI. Every command prints one compact JSON document to stdout."""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from . import analysis as an
from .charts import colour_for, plot
from .report import build
from .resolve import resolve
from .wikimedia import Wikimedia, WikimediaError

MAX_LANGUAGES = 12
# Country codes people (and models) often use instead of Wikipedia edition codes.
ALIASES = {"ua": "uk", "cz": "cs", "vn": "vi", "jp": "ja", "kr": "ko", "gr": "el", "dk": "da", "se": "sv",
           "ee": "et", "by": "be", "cn": "zh", "il": "he", "br": "pt", "ir": "fa", "rs": "sr", "si": "sl",
           "at": "de", "gb": "en", "us": "en", "in": "hi", "my": "ms", "ge": "ka", "am": "hy", "kz": "kk"}


def _out_root() -> Path:
    return Path(os.getenv("WIKI_INTEREST_OUTPUT", "output"))


def _month(s: str) -> date:
    return datetime.strptime(s[:7], "%Y-%m").date()


def last_complete_month(today: date | None = None) -> date:
    t = today or date.today()
    return date(t.year - 1, 12, 1) if t.month == 1 else date(t.year, t.month - 1, 1)


def period_bounds(period: str | None, start: str | None, end: str | None, today: date | None = None):
    limit = last_complete_month(today)
    warnings = []
    e = _month(end) if end else limit
    if e > limit:
        warnings.append(f"end {e:%Y-%m} is not a complete month yet; clamped to {limit:%Y-%m}")
        e = limit
    if start:
        s = _month(start)
    else:
        m = re.fullmatch(r"(\d+)\s*([ym])", (period or "2y").strip().lower())
        if not m:
            raise SystemExit("--period must look like 2y or 18m")
        months = int(m.group(1)) * (12 if m.group(2) == "y" else 1)
        idx = e.year * 12 + e.month - 1 - (months - 1)
        s = date(idx // 12, idx % 12 + 1, 1)
    if s > e:
        raise SystemExit("start is after end")
    return s, e, warnings


def _explicit(items: list[str]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for item in items:
        lang, sep, title = item.partition("=")
        if not sep or not title.strip():
            raise SystemExit(f"--article must be LANG=Title, got {item!r}")
        out.setdefault(lang.strip(), []).append(title.strip())
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "topic"


def _languages(s: str, warnings: list[str] | None = None) -> list[str]:
    langs = []
    for raw in (x.strip().lower() for x in s.split(",") if x.strip()):
        code = ALIASES.get(raw, raw)
        if code != raw and warnings is not None:
            warnings.append(f"interpreted '{raw}' as Wikipedia edition '{code}'")
        if code not in langs:
            langs.append(code)
    if not langs:
        raise SystemExit("--languages is empty")
    if len(langs) > MAX_LANGUAGES:
        raise SystemExit(f"at most {MAX_LANGUAGES} languages per run; split the request")
    return langs


def _auto_next_steps(series: dict, ranking: list[dict]) -> list[str]:
    steps = []
    promising = [r["language"] for r in ranking if (r["share_growth_pct"] or 0) > 0 and r["confidence"] != "low"]
    if promising:
        steps.append(f"Validate demand in {', '.join(promising[:3])} with search-volume data and a localised landing-page test.")
    weak = [lang for lang, m in series.items() if m.get("confidence") == "low"]
    if weak:
        steps.append(f"Treat {', '.join(weak)} as inconclusive: widen the topic with related articles or extend the period.")
    steps.append("Check related articles (sub-topics, competitors' themes) to see whether interest is moving rather than disappearing.")
    return steps


def _auto_text(topic: str, series: dict, ranking: list[dict], missing: list[str]) -> tuple[str, list[str]]:
    findings = []
    for lang, m in series.items():
        if m["direction"] == "insufficient-data":
            findings.append(f"{lang}: not enough complete months to assess a trend.")
            continue
        findings.append(
            f"{lang}: {m['direction']} ({m['growth_basis']}: {m['growth_pct']:+.1f}% raw, "
            f"{m['share_growth_pct']:+.1f}% edition-adjusted); confidence {m['confidence']}"
            + (f" – {m['confidence_reasons'][0]}" if m["confidence_reasons"] else "") + ".")
    if len(ranking) > 1:
        top = ranking[0]
        verb = "grew fastest" if top["share_growth_pct"] > 0 else "declined least"
        rising = [r["language"] for r in ranking if series[r["language"]]["direction"] == "rising"]
        summary = (f"Across {len(ranking)} editions, edition-adjusted interest in {topic} {verb} in "
                   f"{top['language']} ({top['share_growth_pct']:+.1f}%, confidence {top['confidence']}). "
                   + (f"Statistically rising: {', '.join(rising)}." if rising else "No edition shows a clear rising trend."))
    elif ranking:
        m = series[ranking[0]["language"]]
        summary = f"Interest in {topic} in {ranking[0]['language']} Wikipedia: {m['direction']}, confidence {m['confidence']}."
    else:
        summary = f"Not enough data to assess interest in {topic}."
    if missing:
        summary += f" No matching article in: {', '.join(missing)}."
    return summary, findings


def cmd_analyze(a) -> dict:
    start, end, warnings = period_bounds(a.period, a.start, a.end)
    languages = _languages(a.languages, warnings)
    seeds = a.seed or [a.topic]
    wm = Wikimedia()
    editions = {lang: wm.edition_views(lang, start, end, a.access, a.agent) for lang in languages}
    unknown = [lang for lang, e in editions.items() if not e]
    if unknown:
        return {"error": f"no Wikipedia edition with code(s) {', '.join(unknown)}; use ISO 639 edition codes "
                         "such as uk, pl, cs, vi, tr, ja (see https://meta.wikimedia.org/wiki/List_of_Wikipedias)"}
    res = resolve(wm, seeds, languages, a.source_lang, _explicit(a.article))

    months = an.month_range(start, end)
    series, raw_plot, idx_plot, colours, rows, missing = {}, {}, {}, {}, [], []
    for i, lang in enumerate(languages):
        info = res["languages"][lang]
        colours[lang] = colour_for(i)
        arts = [x for x in info["articles"] if x.get("exists", True)]
        if not arts:
            missing.append(lang)
            continue
        if info["status"] == "partial":
            warnings.append(f"{lang}: only {len(arts)}/{len(seeds)} seed articles exist; cluster not fully comparable")
        per_article = [wm.article_views(lang, x["title"], start, end, a.access, a.agent) for x in arts]
        edition = editions[lang]
        kept, values, interior_missing = an.align(months, per_article)
        if interior_missing:
            warnings.append(f"{lang}: {interior_missing} month(s) with no recorded views counted as 0")
        if kept and kept[0] != months[0]:
            warnings.append(f"{lang}: data starts {kept[0]} (article created later)")
        m = an.analyse_series(kept, values, edition, a.window)
        m["articles"] = [x["title"] for x in arts]
        series[lang] = m
        if kept:
            raw_plot[lang] = (kept, values)
            share = [v / edition[k] * 1e6 if edition.get(k) else 0 for k, v in zip(kept, values)]
            base = sum(share[:12]) / min(12, len(share)) or 1
            idx_plot[lang] = (kept, [s / base * 100 for s in share])
        for k, v in zip(kept, values):
            rows.append({"language": lang, "month": k, "views": v, "edition_views": edition.get(k, 0)})

    ranking = an.rank(series)
    summary, findings = _auto_text(a.topic, series, ranking, missing)
    run_id = f"{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{_slug(a.topic)}"
    out = _out_root() / run_id
    out.mkdir(parents=True, exist_ok=True)
    result = {
        "run_id": run_id, "topic": a.topic,
        "params": {"languages": languages, "seeds": seeds, "source_lang": a.source_lang,
                   "start": str(start), "end": str(end), "window": a.window,
                   "access": a.access, "agent": a.agent, "explicit_articles": a.article},
        "resolution": res, "series": series, "ranking": ranking, "missing_languages": missing,
        "warnings": warnings, "auto_summary": summary, "auto_findings": findings,
        "auto_next_steps": _auto_next_steps(series, ranking),
        "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cache": {"hits": wm.cache.hits, "misses": wm.cache.misses, "http_requests": wm.requests_made},
    }
    with open(out / "observations.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["language", "month", "views", "edition_views"])
        w.writeheader()
        w.writerows(rows)
    artifacts = {"analysis": str(out / "analysis.json"), "data": str(out / "observations.csv")}
    if raw_plot:
        artifacts["chart"] = plot(raw_plot, idx_plot, colours, str(out / "chart.png"), a.topic)
        if not a.no_pdf:
            artifacts["pdf"] = build(result, artifacts["chart"], str(out / "report.pdf"))
    result["artifacts"] = artifacts
    (out / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return compact(result)


def compact(r: dict) -> dict:
    """What the agent needs to reason - kept small for cheap models. Full detail stays in analysis.json."""
    keys = ["articles", "months", "median_monthly_views", "growth_pct", "share_growth_pct", "edition_growth_pct",
            "start_vs_end_pct", "months_up_vs_year_before", "theil_sen_pct_per_year", "seasonality_strength", "spike_months",
            "direction", "confidence", "confidence_reasons"]
    series = {}
    for lang, m in r["series"].items():
        s = {k: m[k] for k in keys if k in m}
        if "trend_test" in m:
            s["trend_p"] = m["trend_test"]["p_value"]
            s["share_trend_p"] = m["share_trend_test"]["p_value"]
        series[lang] = s
    unresolved = {lang: v["missing"] for lang, v in r["resolution"]["languages"].items() if v["missing"]}
    return {"run_id": r["run_id"], "topic": r["topic"], "period": f"{r['params']['start'][:7]}..{r['params']['end'][:7]}",
            "growth_basis": next(iter(r["series"].values()), {}).get("growth_basis"),
            "series": series, "ranking": r["ranking"], "missing_languages": r["missing_languages"],
            "unresolved": unresolved, "warnings": r["warnings"], "auto_summary": r["auto_summary"],
            "artifacts": r.get("artifacts", {}), "cache": r.get("cache"),
            "next_action": (f"If the user asked for a report, run: report --run {r['run_id']} --summary \"...\" "
                            "--finding \"...\" --next-step \"...\" with your own conclusions, then link the PDF. "
                            "Answer follow-up questions about this data from this output or `show`, without re-running analyze.")}


def _load(run_id: str) -> dict:
    p = _out_root() / run_id / "analysis.json"
    if not p.exists():
        raise SystemExit(f"unknown run {run_id!r}; use `runs` to list available runs")
    return json.loads(p.read_text(encoding="utf-8"))


def cmd_report(a) -> dict:
    r = _load(a.run)
    out = _out_root() / a.run
    pdf = build(r, str(out / "chart.png"), str(out / "report.pdf"), a.summary, a.finding or None, a.next_step or None)
    return {"run_id": a.run, "pdf": pdf}


def cmd_runs(a) -> dict:
    root = _out_root()
    runs = []
    for p in sorted(root.glob("*/analysis.json"), reverse=True)[: a.limit]:
        r = json.loads(p.read_text(encoding="utf-8"))
        runs.append({"run_id": r["run_id"], "topic": r["topic"], "languages": r["params"]["languages"],
                     "period": f"{r['params']['start'][:7]}..{r['params']['end'][:7]}", "seeds": r["params"]["seeds"]})
    return {"runs": runs}


def cmd_show(a) -> dict:
    r = _load(a.run)
    if a.language:
        return {"run_id": a.run, "language": a.language, "metrics": r["series"].get(a.language),
                "resolution": r["resolution"]["languages"].get(a.language)}
    return compact(r)


def cmd_resolve(a) -> dict:
    wm = Wikimedia()
    return resolve(wm, a.seed or [a.topic], _languages(a.languages), a.source_lang, _explicit(a.article))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki-interest", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    def topic_args(sp):
        sp.add_argument("--topic", required=True, help="human-readable topic name (report title)")
        sp.add_argument("--seed", action="append", default=[],
                        help="article title in --source-lang; repeat to build a topic cluster (default: --topic)")
        sp.add_argument("--languages", required=True, help="comma-separated edition codes, e.g. pl,cs,uk")
        sp.add_argument("--source-lang", default="en", help="language of --seed titles (default en)")
        sp.add_argument("--article", action="append", default=[], help="LANG=Exact title; overrides lookup for LANG")

    an_ = sub.add_parser("analyze", help="fetch, analyse, chart and report")
    topic_args(an_)
    an_.add_argument("--period", default=None, help="e.g. 2y (default) or 18m, ending at last complete month")
    an_.add_argument("--start", help="YYYY-MM (overrides --period)")
    an_.add_argument("--end", help="YYYY-MM (default: last complete month)")
    an_.add_argument("--window", type=int, default=6, help="months for start-vs-end comparison (default 6)")
    an_.add_argument("--access", default="all-access", choices=["all-access", "desktop", "mobile-web", "mobile-app"])
    an_.add_argument("--agent", default="user", choices=["user", "all-agents", "automated", "spider"])
    an_.add_argument("--no-pdf", action="store_true")
    an_.set_defaults(fn=cmd_analyze)

    rs = sub.add_parser("resolve", help="only map the topic to articles per language")
    topic_args(rs)
    rs.set_defaults(fn=cmd_resolve)

    rp = sub.add_parser("report", help="re-render a run's PDF with your own summary/findings/next steps")
    rp.add_argument("--run", required=True)
    rp.add_argument("--summary")
    rp.add_argument("--finding", action="append", default=[])
    rp.add_argument("--next-step", action="append", default=[])
    rp.set_defaults(fn=cmd_report)

    ru = sub.add_parser("runs", help="list previous runs (newest first)")
    ru.add_argument("--limit", type=int, default=10)
    ru.set_defaults(fn=cmd_runs)

    sh = sub.add_parser("show", help="print a previous run without refetching")
    sh.add_argument("--run", required=True)
    sh.add_argument("--language")
    sh.set_defaults(fn=cmd_show)
    return p


def main(argv: list[str] | None = None) -> int:
    p = parser()
    a, unknown = p.parse_known_args(argv)
    if unknown and a.command not in ("show", "runs"):
        p.error(f"unrecognized arguments: {' '.join(unknown)}")  # never silently change an analysis
    ignored = {"ignored_arguments": unknown} if unknown else {}
    try:
        result = a.fn(a)
    except WikimediaError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({**result, **ignored}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
