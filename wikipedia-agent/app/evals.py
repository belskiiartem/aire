"""Run the skill's end-to-end scenarios against a model: python -m app.evals [--model gpt-4.1-nano] [--case id]."""
from __future__ import annotations

import argparse
import json
import time

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver

from . import config
from .graph import build_graph


def _check(case: dict, answer: str, calls: list[dict]) -> list[str]:
    failures = []
    flat = " ".join(json.dumps(c["args"], ensure_ascii=False) for c in calls)
    low = answer.lower()
    for token in case.get("expect_tool_args", []):
        if token not in flat:
            failures.append(f"tool args missing {token!r}")
    for group in case.get("expect_tool_args_any", []):
        if not any(t in flat for t in group):
            failures.append(f"tool args missing any of {group}")
    for group in case.get("expect_answer_any", []) + case.get("expect_answer_all_any", []):
        if not any(t.lower() in low for t in group):
            failures.append(f"answer missing any of {group}")
    for token in case.get("forbid_answer", []):
        if token.lower() in low:
            failures.append(f"answer contains forbidden {token!r}")
    analyze = sum(1 for c in calls if " analyze " in f' {c["args"].get("command", "")} ')
    if "max_analyze_calls" in case and analyze > case["max_analyze_calls"]:
        failures.append(f"{analyze} analyze calls > {case['max_analyze_calls']}")
    return failures


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=config.LLM_MODEL)
    p.add_argument("--case", action="append")
    p.add_argument("--show-answers", action="store_true")
    a = p.parse_args()
    cases = json.loads((config.SKILLS_DIR / "wikipedia-interest" / "evals" / "evals.json").read_text())["cases"]
    graph = build_graph(a.model, InMemorySaver())
    threads: dict[str, str] = {}
    results = []
    for case in cases:
        if a.case and case["id"] not in a.case and case.get("after") not in (a.case or []):
            continue
        thread = threads.get(case.get("after"), case["id"])
        threads[case["id"]] = thread
        cfg = {"configurable": {"thread_id": thread}, "recursion_limit": config.MAX_STEPS * 2}
        before = len(graph.get_state(cfg).values.get("messages", []))
        t0 = time.monotonic()
        try:
            state = graph.invoke({"messages": [HumanMessage(case["prompt"])]}, cfg)
            new = state["messages"][before:]
            answer = new[-1].content
            calls = [{"name": c["name"], "args": c["args"]} for m in new for c in (getattr(m, "tool_calls", None) or [])]
            tokens = sum((getattr(m, "usage_metadata", None) or {}).get("total_tokens", 0) for m in new)
            failures = _check(case, answer, calls)
        except Exception as exc:
            answer, calls, tokens, failures = "", [], 0, [f"{type(exc).__name__}: {exc}"]
        results.append({"id": case["id"], "pass": not failures, "failures": failures, "tool_calls": len(calls),
                        "tokens": tokens, "seconds": round(time.monotonic() - t0, 1)})
        status = "PASS" if not failures else "FAIL"
        print(f"{status} {case['id']:28} calls={len(calls):2} tokens={tokens:6} {results[-1]['seconds']:5}s {failures or ''}")
        for c in calls:
            print("    ", c["name"], json.dumps(c["args"], ensure_ascii=False)[:300])
        if a.show_answers:
            print("----\n" + answer + "\n----")
    passed = sum(r["pass"] for r in results)
    print(f"\nmodel={a.model}  passed {passed}/{len(results)}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
