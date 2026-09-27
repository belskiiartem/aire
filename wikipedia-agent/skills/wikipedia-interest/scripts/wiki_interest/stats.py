"""Small, dependency-free statistics for short monthly series.

Chosen for robustness on 12-60 noisy points rather than elegance:
* Theil-Sen slope      - median of pairwise slopes, insensitive to a few spikes.
* Seasonal Mann-Kendall - monotonic-trend test comparing the same calendar month
  across years, so a recurring January peak is not mistaken for growth.
"""
from __future__ import annotations

import math
import statistics


def theil_sen(y: list[float]) -> float:
    slopes = [(y[j] - y[i]) / (j - i) for i in range(len(y)) for j in range(i + 1, len(y))]
    return statistics.median(slopes) if slopes else 0.0


def _mk_s_var(y: list[float]) -> tuple[float, float]:
    n = len(y)
    s = sum((y[j] > y[i]) - (y[j] < y[i]) for i in range(n) for j in range(i + 1, n))
    ties: dict[float, int] = {}
    for v in y:
        ties[v] = ties.get(v, 0) + 1
    var = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties.values())) / 18
    return s, var


def _p_two_sided(s: float, var: float) -> float:
    if var <= 0:
        return 1.0
    z = (s - 1) / math.sqrt(var) if s > 0 else (s + 1) / math.sqrt(var) if s < 0 else 0.0
    return math.erfc(abs(z) / math.sqrt(2))


def mann_kendall(y: list[float], period: int = 12) -> dict:
    """Seasonal MK when there are >= 2 full cycles, plain MK otherwise."""
    seasonal = len(y) >= 2 * period
    if seasonal:
        s_tot = var_tot = 0.0
        for m in range(period):
            sub = y[m::period]
            if len(sub) >= 2:
                s, v = _mk_s_var(sub)
                s_tot += s
                var_tot += v
    else:
        s_tot, var_tot = _mk_s_var(y)
    return {"test": "seasonal-mann-kendall" if seasonal else "mann-kendall",
            "s": int(s_tot), "p_value": round(_p_two_sided(s_tot, var_tot), 4)}


def seasonality_strength(y: list[float], period: int = 12) -> float | None:
    """Share of variance explained by calendar month (0..1) after removing the linear trend."""
    if len(y) < 2 * period:
        return None
    slope = theil_sen(y)
    detr = [v - slope * i for i, v in enumerate(y)]
    total = statistics.pvariance(detr)
    if total == 0:
        return 0.0
    means = [statistics.fmean(detr[m::period]) for m in range(period)]
    fitted = [means[i % period] for i in range(len(detr))]
    return round(statistics.pvariance(fitted) / total, 3)


def pct(new: float, old: float) -> float | None:
    return None if not old else round((new / old - 1) * 100, 1)
