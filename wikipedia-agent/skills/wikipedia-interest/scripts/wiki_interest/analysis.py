"""Turn raw monthly series into comparable, validated metrics."""
from __future__ import annotations

import statistics
from datetime import date

from .stats import mann_kendall, pct, seasonality_strength, theil_sen

SPIKE_FACTOR = 3.0      # a month above 3x the median is treated as a spike
MIN_MONTHS = 12


def month_range(start: date, end: date) -> list[str]:
    out, y, m = [], start.year, start.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y:04d}-{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def align(months: list[str], series_list: list[dict[str, int]]) -> tuple[list[str], list[int], int]:
    """Sum several article series; drop leading months before any article existed.

    Returns (months, values, interior_missing_count).
    """
    first = next((i for i, m in enumerate(months) if any(m in s for s in series_list)), None)
    if first is None:
        return [], [], 0
    kept = months[first:]
    values, missing = [], 0
    for m in kept:
        present = [s[m] for s in series_list if m in s]
        missing += not present
        values.append(sum(present))
    return kept, values, missing


def _growth(y: list[float], window: int) -> tuple[float | None, str]:
    if len(y) >= 24:
        return pct(sum(y[-12:]), sum(y[-24:-12])), "last 12 months vs previous 12"
    if len(y) >= 2 * window:
        return pct(sum(y[-window:]), sum(y[-2 * window:-window])), f"last {window} months vs previous {window}"
    return None, "insufficient data"


def analyse_series(months: list[str], views: list[int], edition: dict[str, int], window: int = 6) -> dict:
    n = len(views)
    if n < MIN_MONTHS:
        return {"months": n, "direction": "insufficient-data", "confidence": "low",
                "confidence_reasons": [f"only {n} complete months (need >= {MIN_MONTHS})"]}
    y = [float(v) for v in views]
    ed = [float(edition.get(m, 0)) for m in months]
    share = [v / e * 1e6 if e else 0.0 for v, e in zip(y, ed)]  # views per million edition views
    med = statistics.median(y)

    growth, basis = _growth(y, window)
    share_growth, _ = _growth(share, window)
    edition_growth, _ = _growth(ed, window)
    mk = mann_kendall(y)
    mk_share = mann_kendall(share)
    slope_pct_year = round(theil_sen(y) * 12 / med * 100, 1) if med else None

    spikes = [m for m, v in zip(months, y) if med and v > SPIKE_FACTOR * med]
    despiked = [min(v, SPIKE_FACTOR * med) if med else v for v in y]
    growth_despiked, _ = _growth(despiked, window)
    spike_driven = bool(spikes) and growth is not None and growth_despiked is not None and (
        (growth > 0) != (growth_despiked > 0) or abs(growth_despiked) < abs(growth) / 2)

    # plain-language consistency check: how many of the last 12 months beat the same month a year earlier
    yoy_up = sum(y[i] > y[i - 12] for i in range(max(12, n - 12), n)) if n >= 24 else None

    # first/last `window` months, handy for "compare the start and the end" follow-ups
    start_vs_end = pct(sum(y[-window:]), sum(y[:window]))

    p = mk["p_value"]
    if growth is not None and growth > 5 and p < 0.10:
        direction = "rising"
    elif growth is not None and growth < -5 and p < 0.10:
        direction = "falling"
    else:
        direction = "no clear trend"

    score, reasons = 0.0, []
    if n >= 24:
        score += 1
    else:
        reasons.append(f"only {n} months; seasonality cannot be separated from trend")
    if p < 0.05:
        score += 1
    elif p < 0.10:
        score += 0.5
        reasons.append(f"trend test borderline (p={p})")
    else:
        reasons.append(f"trend not statistically distinguishable from noise (p={p})")
    if spike_driven:
        reasons.append(f"change is driven by spike month(s) {', '.join(spikes)}")
    else:
        score += 1
    if med >= 1000:
        score += 1
    elif med >= 300:
        score += 0.5
        reasons.append(f"modest volume (median {int(med)} views/month)")
    else:
        reasons.append(f"low volume (median {int(med)} views/month) - small absolute changes swing percentages")
    if growth is not None and share_growth is not None and (growth > 0) == (share_growth > 0):
        score += 1
    elif growth is not None:
        reasons.append("raw trend disappears after adjusting for overall edition traffic "
                       f"(edition {edition_growth:+.1f}%)" if edition_growth is not None else
                       "raw and edition-adjusted trends disagree")
    confidence = "high" if score >= 4 else "medium" if score >= 2.5 else "low"
    disagree = growth is not None and share_growth is not None and (growth > 0) != (share_growth > 0)
    if confidence == "high" and (med < 300 or disagree):
        # low volume: a few dozen readers flip the result; disagreement: topic vs edition-wide effect is unclear
        confidence = "medium"

    return {
        "months": n, "period": f"{months[0]}..{months[-1]}",
        "median_monthly_views": int(med), "total_views": int(sum(y)),
        "growth_pct": growth, "growth_basis": basis,
        "share_growth_pct": share_growth, "edition_growth_pct": edition_growth,
        "start_vs_end_pct": start_vs_end, "start_vs_end_basis": f"last {window} vs first {window} months",
        "theil_sen_pct_per_year": slope_pct_year,
        "months_up_vs_year_before": None if yoy_up is None else f"{yoy_up}/12",
        "trend_test": mk, "share_trend_test": mk_share,
        "seasonality_strength": seasonality_strength(y),
        "spike_months": spikes, "growth_without_spikes_pct": growth_despiked, "spike_driven": spike_driven,
        "direction": direction, "confidence": confidence, "confidence_score": score,
        "confidence_reasons": reasons,
    }


def rank(series: dict[str, dict]) -> list[dict]:
    """Transparent ordering: edition-adjusted growth, ties broken by confidence then volume."""
    order = {"high": 0, "medium": 1, "low": 2}
    rows = [
        {"language": lang, "share_growth_pct": m.get("share_growth_pct"), "growth_pct": m.get("growth_pct"),
         "confidence": m.get("confidence"), "median_monthly_views": m.get("median_monthly_views")}
        for lang, m in series.items() if m.get("share_growth_pct") is not None
    ]
    rows.sort(key=lambda r: (-r["share_growth_pct"], order.get(r["confidence"], 3), -(r["median_monthly_views"] or 0)))
    return rows
