"""Map a topic to the *same* article in several language editions.

Strategy (most to least reliable):
1. explicit `lang=Title` supplied by the caller  -> method "explicit"
2. seed article in the source language, followed through Wikidata interlanguage
   links to every target language                -> method "langlink"
3. nothing found                                  -> status "missing" with *unverified*
   local search candidates. These are never analysed automatically: a keyword
   search in another language frequently returns unrelated pages.
"""
from __future__ import annotations

from .wikimedia import Wikimedia


def resolve_seed(wm: Wikimedia, seed: str, source_lang: str) -> dict:
    page = wm.page_with_langlinks(source_lang, seed)
    if page is None:
        candidates = wm.search(source_lang, seed)
        for cand in candidates[:1]:
            page = wm.page_with_langlinks(source_lang, cand)
            if page:
                return {"seed": seed, "source_title": page["title"], "wikidata": page["wikidata"],
                        "langlinks": page["langlinks"], "disambiguation": page["disambiguation"],
                        "note": f"'{seed}' not found in {source_lang}; used top search hit '{cand}'",
                        "search_candidates": candidates}
        return {"seed": seed, "source_title": None, "wikidata": None, "langlinks": {},
                "note": f"'{seed}' not found in {source_lang} Wikipedia", "search_candidates": candidates}
    return {"seed": seed, "source_title": page["title"], "wikidata": page["wikidata"],
            "langlinks": page["langlinks"], "disambiguation": page["disambiguation"], "note": None}


def resolve(wm: Wikimedia, seeds: list[str], languages: list[str], source_lang: str,
            explicit: dict[str, list[str]]) -> dict:
    """Return {"seeds": [...], "languages": {lang: {"articles": [...], "missing": [...], ...}}}."""
    seed_info = [resolve_seed(wm, s, source_lang) for s in seeds]
    out: dict[str, dict] = {}
    for lang in languages:
        if lang in explicit:
            arts = []
            for title in explicit[lang]:
                page = wm.page_with_langlinks(lang, title)
                arts.append({"title": page["title"] if page else title, "method": "explicit",
                             "exists": page is not None})
            out[lang] = {"articles": arts, "missing": [], "status": "ok" if any(a["exists"] for a in arts) else "missing"}
            continue
        arts, missing = [], []
        for info in seed_info:
            if info["source_title"] is None:
                missing.append({"seed": info["seed"], "reason": "seed not found in source language"})
                continue
            if lang == source_lang:
                arts.append({"title": info["source_title"], "method": "source", "seed": info["seed"]})
            elif lang in info["langlinks"]:
                arts.append({"title": info["langlinks"][lang], "method": "langlink", "seed": info["seed"],
                             "wikidata": info["wikidata"]})
            else:
                missing.append({"seed": info["seed"], "reason": f"no {lang} article linked to {info['wikidata']}",
                                "unverified_candidates": wm.search(lang, info["source_title"], limit=3)})
        status = "ok" if arts and not missing else ("partial" if arts else "missing")
        out[lang] = {"articles": arts, "missing": missing, "status": status}
    return {"source_lang": source_lang, "seeds": seed_info, "languages": out}
