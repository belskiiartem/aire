"""Offline tests - no network. Each case pins a bug found while building the skill."""
import json
import math
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from wiki_interest import analysis as an  # noqa: E402
from wiki_interest import cli, stats  # noqa: E402
from wiki_interest.resolve import resolve  # noqa: E402
from wiki_interest.wikimedia import Cache, Wikimedia  # noqa: E402


# ------------------------------------------------------------------ dates
def test_period_ends_at_last_complete_month():
    s, e, warnings = cli.period_bounds("2y", None, None, today=date(2026, 9, 27))
    assert (s, e, warnings) == (date(2024, 9, 1), date(2026, 8, 1), [])


def test_incomplete_end_month_is_clamped_with_warning():
    _, e, warnings = cli.period_bounds(None, "2025-01", "2026-09", today=date(2026, 9, 27))
    assert e == date(2026, 8, 1) and "clamped" in warnings[0]


def test_monthly_request_uses_last_day_of_end_month(tmp_path):
    """Passing the 1st of the end month returned a single day labelled as the whole month."""
    wm = Wikimedia(Cache(tmp_path / "c.sqlite"))
    urls = []
    wm._get = lambda url, params=None, allow_404=False: urls.append(url) or {"items": []}
    wm.article_views("de", "Astronomie", date(2024, 9, 1), date(2026, 2, 1))
    assert urls[0].endswith("/monthly/2024090100/2026022800")


def test_cache_prevents_second_request(tmp_path):
    wm = Wikimedia(Cache(tmp_path / "c.sqlite"))
    calls = []
    wm._get = lambda url, params=None, allow_404=False: calls.append(url) or {
        "items": [{"timestamp": "2025010100", "views": 5}]}
    wm.article_views("uk", "Астрономія", date(2025, 1, 1), date(2025, 1, 1))
    assert wm.article_views("uk", "Астрономія", date(2025, 1, 1), date(2025, 1, 1)) == {"2025-01": 5}
    assert len(calls) == 1 and wm.cache.hits == 1


# ------------------------------------------------------------- resolution
class FakeWM:
    def __init__(self, pages, search=None):
        self.pages, self._search = pages, search or {}

    def page_with_langlinks(self, lang, title):
        return self.pages.get((lang, title))

    def search(self, lang, query, limit=5):
        return self._search.get(lang, [])[:limit]


def test_missing_language_never_falls_back_to_search_hit():
    """pl has no 'Intermittent fasting' article; keyword search returned 'Stres oksydacyjny'."""
    wm = FakeWM({("en", "Intermittent fasting"): {"title": "Intermittent fasting", "wikidata": "Q1666254",
                                                   "disambiguation": False,
                                                   "langlinks": {"cs": "Přerušovaný půst"}}},
                search={"pl": ["Stres oksydacyjny"]})
    res = resolve(wm, ["Intermittent fasting"], ["pl", "cs"], "en", {})
    assert res["languages"]["cs"]["articles"][0]["title"] == "Přerušovaný půst"
    assert res["languages"]["pl"]["articles"] == []
    assert res["languages"]["pl"]["status"] == "missing"
    assert res["languages"]["pl"]["missing"][0]["unverified_candidates"] == ["Stres oksydacyjny"]


def test_explicit_article_overrides_lookup():
    wm = FakeWM({("pl", "Post przerywany"): {"title": "Post przerywany", "wikidata": None,
                                             "disambiguation": False, "langlinks": {}}})
    res = resolve(wm, ["Intermittent fasting"], ["pl"], "en", {"pl": ["Post przerywany"]})
    assert res["languages"]["pl"]["articles"][0]["method"] == "explicit"


# ------------------------------------------------------------------ stats
def test_mann_kendall_detects_steady_growth_and_ignores_pure_seasonality():
    growth = [100 + 5 * i for i in range(24)]
    seasonal = [round(100 + 50 * math.sin(2 * math.pi * i / 12)) for i in range(36)]  # views are integers
    assert stats.mann_kendall(growth)["p_value"] < 0.01
    assert stats.mann_kendall(seasonal)["p_value"] > 0.5


def test_theil_sen_is_robust_to_a_spike():
    y = [100.0] * 24
    y[10] = 5000
    assert stats.theil_sen(y) == 0


# --------------------------------------------------------------- analysis
def _months(n, start=date(2024, 9, 1)):
    return an.month_range(start, date(start.year + (start.month - 1 + n - 1) // 12,
                                      (start.month - 1 + n - 1) % 12 + 1, 1))


def test_single_spike_is_flagged_and_lowers_confidence():
    m = _months(24)
    views = [1000] * 24
    views[20] = 20000
    r = an.analyse_series(m, views, {k: 10**8 for k in m})
    assert r["spike_driven"] and r["spike_months"] == [m[20]]
    assert r["confidence"] != "high"


def test_low_volume_caps_confidence_at_medium():
    m = _months(24)
    views = [100 + 4 * i for i in range(24)]
    r = an.analyse_series(m, views, {k: 10**8 for k in m})
    assert r["direction"] == "rising" and r["confidence"] == "medium"


def test_edition_wide_growth_is_not_topic_growth():
    m = _months(24)
    views = [2000 + 40 * i for i in range(24)]
    edition = {k: 10**8 * (1 + 0.05 * i) for i, k in enumerate(m)}   # edition grows faster
    r = an.analyse_series(m, views, edition)
    assert r["growth_pct"] > 0 and r["share_growth_pct"] < 0
    assert any("edition" in x for x in r["confidence_reasons"])


def test_align_drops_months_before_article_existed():
    months = ["2025-01", "2025-02", "2025-03"]
    kept, values, missing = an.align(months, [{"2025-02": 5, "2025-03": 7}])
    assert kept == ["2025-02", "2025-03"] and values == [5, 7] and missing == 0


# -------------------------------------------------------------- end to end
def test_analyze_end_to_end_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("WIKI_INTEREST_OUTPUT", str(tmp_path / "out"))
    monkeypatch.setenv("WIKI_INTEREST_CACHE", str(tmp_path / "cache"))
    pages = {("en", "Astronomy"): {"title": "Astronomy", "wikidata": "Q333", "disambiguation": False,
                                   "langlinks": {"uk": "Астрономія", "pl": "Astronomia"}}}
    monkeypatch.setattr(Wikimedia, "page_with_langlinks", lambda self, l, t: pages.get((l, t)))
    monkeypatch.setattr(Wikimedia, "search", lambda self, l, q, limit=5: [])

    def views(self, lang, title, start, end, access="all-access", agent="user"):
        base = 1500 if lang == "uk" else 3000
        return {m: base + (30 if lang == "uk" else -40) * i for i, m in enumerate(an.month_range(start, end))}

    monkeypatch.setattr(Wikimedia, "article_views", views)
    monkeypatch.setattr(Wikimedia, "edition_views",
                        lambda self, lang, s, e, *a: {m: 10**8 for m in an.month_range(s, e)})
    out = cli.cmd_analyze(cli.parser().parse_args(
        ["analyze", "--topic", "Astronomy", "--languages", "uk,pl", "--start", "2024-09", "--end", "2026-08"]))
    assert out["series"]["uk"]["direction"] == "rising"
    assert out["series"]["pl"]["direction"] == "falling"
    assert out["ranking"][0]["language"] == "uk"
    pdf = Path(out["artifacts"]["pdf"]).read_bytes()
    assert pdf.count(b"/Type /Page\n") + pdf.count(b"/Type /Page ") + pdf.count(b"/Type /Page>") <= 1 or b"/Count 1" in pdf

    # follow-up commands work from disk only
    runs = cli.cmd_runs(cli.parser().parse_args(["runs"]))["runs"]
    assert runs[0]["run_id"] == out["run_id"]
    rep = cli.cmd_report(cli.parser().parse_args(
        ["report", "--run", out["run_id"], "--summary", "Custom", "--next-step", "Survey uk users"]))
    assert Path(rep["pdf"]).exists()
    full = json.loads(Path(out["artifacts"]["analysis"]).read_text())
    assert full["resolution"]["languages"]["uk"]["articles"][0]["method"] == "langlink"
