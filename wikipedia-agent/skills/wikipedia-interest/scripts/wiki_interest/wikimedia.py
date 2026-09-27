"""Wikimedia REST / MediaWiki Action API client with a local SQLite cache.

Only *complete* months are ever requested, and a complete month never changes,
so cached pageview rows are treated as immutable. Title resolution results are
cached with a TTL because articles can be created or renamed.
"""
from __future__ import annotations

import calendar
import json
import os
import sqlite3
import time
from datetime import date
from pathlib import Path
from urllib.parse import quote

import requests

REST = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
DEFAULT_UA = "wikipedia-interest-skill/0.2 (https://github.com/belskiiartem/aire)"
RESOLUTION_TTL_S = 7 * 24 * 3600


class WikimediaError(RuntimeError):
    pass


def _user_agent() -> str:
    return os.getenv("WIKI_USER_AGENT", DEFAULT_UA)


def _stamp(d: date) -> str:
    return d.strftime("%Y%m%d") + "00"


def _month_end(d: date) -> date:
    # The per-article endpoint truncates a monthly bucket at the end *day*: passing the
    # 1st of the month returns a single day of views labelled as the whole month.
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def _cache_path() -> Path:
    base = os.getenv("WIKI_INTEREST_CACHE") or os.path.join(
        os.getenv("XDG_CACHE_HOME", os.path.expanduser("~/.cache")), "wiki-interest"
    )
    p = Path(base)
    p.mkdir(parents=True, exist_ok=True)
    return p / "cache.sqlite"


class Cache:
    def __init__(self, path: Path | None = None):
        self.db = sqlite3.connect(path or _cache_path())
        self.db.executescript(
            """
            CREATE TABLE IF NOT EXISTS views (
                key TEXT, month TEXT, views INTEGER, PRIMARY KEY (key, month));
            CREATE TABLE IF NOT EXISTS fetched (
                key TEXT, start TEXT, end TEXT, fetched_at REAL);
            CREATE TABLE IF NOT EXISTS kv (
                key TEXT PRIMARY KEY, value TEXT, fetched_at REAL);
            """
        )
        self.hits = 0
        self.misses = 0

    def covered(self, key: str, start: str, end: str) -> bool:
        row = self.db.execute(
            "SELECT 1 FROM fetched WHERE key=? AND start<=? AND end>=? LIMIT 1", (key, start, end)
        ).fetchone()
        return row is not None

    def read_views(self, key: str, start: str, end: str) -> dict[str, int]:
        rows = self.db.execute(
            "SELECT month, views FROM views WHERE key=? AND month>=? AND month<=?", (key, start, end)
        )
        return dict(rows.fetchall())

    def write_views(self, key: str, start: str, end: str, series: dict[str, int]) -> None:
        self.db.executemany(
            "INSERT OR REPLACE INTO views VALUES (?,?,?)", [(key, m, v) for m, v in series.items()]
        )
        self.db.execute("INSERT INTO fetched VALUES (?,?,?,?)", (key, start, end, time.time()))
        self.db.commit()

    def get(self, key: str, ttl: float | None = None):
        row = self.db.execute("SELECT value, fetched_at FROM kv WHERE key=?", (key,)).fetchone()
        if row and (ttl is None or time.time() - row[1] < ttl):
            return json.loads(row[0])
        return None

    def put(self, key: str, value) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO kv VALUES (?,?,?)", (key, json.dumps(value, ensure_ascii=False), time.time())
        )
        self.db.commit()


class Wikimedia:
    def __init__(self, cache: Cache | None = None, timeout: float = 30, retries: int = 4):
        self.cache = cache or Cache()
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _user_agent(), "Accept": "application/json"})
        self.requests_made = 0

    # ---------------------------------------------------------------- HTTP
    def _get(self, url: str, params: dict | None = None, allow_404: bool = False):
        last = None
        for attempt in range(self.retries):
            try:
                self.requests_made += 1
                r = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last = str(exc)
            else:
                if r.status_code == 200:
                    return r.json()
                if r.status_code == 404 and allow_404:
                    return None
                if r.status_code != 429 and r.status_code < 500:
                    raise WikimediaError(f"HTTP {r.status_code} for {url}: {r.text[:300]}")
                last = f"HTTP {r.status_code}"
            time.sleep(min(2**attempt, 8))
        raise WikimediaError(f"request failed after {self.retries} attempts ({last}): {url}")

    # ----------------------------------------------------------- pageviews
    def _monthly(self, key: str, url_prefix: str, start: date, end: date) -> dict[str, int]:
        """Monthly views keyed by 'YYYY-MM'. `start`/`end` are first days of months, inclusive."""
        s, e = start.strftime("%Y-%m"), end.strftime("%Y-%m")
        if self.cache.covered(key, s, e):
            self.cache.hits += 1
            return self.cache.read_views(key, s, e)
        self.cache.misses += 1
        payload = self._get(f"{url_prefix}/monthly/{_stamp(start)}/{_stamp(_month_end(end))}", allow_404=True)
        series = {}
        for item in (payload or {}).get("items", []):
            ts = item["timestamp"]
            series[f"{ts[:4]}-{ts[4:6]}"] = int(item["views"])
        self.cache.write_views(key, s, e, series)
        return series

    def article_views(self, lang: str, title: str, start: date, end: date,
                      access: str = "all-access", agent: str = "user") -> dict[str, int]:
        project = f"{lang}.wikipedia.org"
        t = quote(title.replace(" ", "_"), safe="")
        key = f"article|{project}|{access}|{agent}|{title}"
        return self._monthly(key, f"{REST}/per-article/{project}/{access}/{agent}/{t}", start, end)

    def edition_views(self, lang: str, start: date, end: date,
                      access: str = "all-access", agent: str = "user") -> dict[str, int]:
        project = f"{lang}.wikipedia.org"
        key = f"aggregate|{project}|{access}|{agent}"
        return self._monthly(key, f"{REST}/aggregate/{project}/{access}/{agent}", start, end)

    # ------------------------------------------------------- title lookup
    def _action(self, lang: str, params: dict):
        return self._get(f"https://{lang}.wikipedia.org/w/api.php",
                         {**params, "format": "json", "formatversion": 2})

    def page_with_langlinks(self, lang: str, title: str) -> dict | None:
        """Canonical title (redirects followed), Wikidata id and all interlanguage links."""
        key = f"page|{lang}|{title}"
        cached = self.cache.get(key, RESOLUTION_TTL_S)
        if cached is not None:
            return cached or None
        data = self._action(lang, {"action": "query", "titles": title, "redirects": 1,
                                   "prop": "langlinks|pageprops", "ppprop": "wikibase_item|disambiguation",
                                   "lllimit": "max"})
        pages = data.get("query", {}).get("pages", [])
        page = pages[0] if pages else {}
        if not page or page.get("missing") or page.get("invalid"):
            self.cache.put(key, {})
            return None
        result = {
            "title": page["title"],
            "wikidata": page.get("pageprops", {}).get("wikibase_item"),
            "disambiguation": "disambiguation" in page.get("pageprops", {}),
            "langlinks": {ll["lang"]: ll["title"] for ll in page.get("langlinks", [])},
        }
        self.cache.put(key, result)
        return result

    def search(self, lang: str, query: str, limit: int = 5) -> list[str]:
        key = f"search|{lang}|{query}|{limit}"
        cached = self.cache.get(key, RESOLUTION_TTL_S)
        if cached is not None:
            return cached
        data = self._action(lang, {"action": "query", "list": "search", "srsearch": query, "srlimit": limit})
        titles = [h["title"] for h in data.get("query", {}).get("search", [])]
        self.cache.put(key, titles)
        return titles
