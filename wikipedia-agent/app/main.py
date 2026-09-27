"""HTTP API: POST /chat, GET /artifacts/..., GET /healthz, GET / (minimal web chat)."""
from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from . import config

if config.PHOENIX_COLLECTOR_ENDPOINT:
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    LangChainInstrumentor().instrument(tracer_provider=register(project_name=config.PHOENIX_PROJECT, batch=True))

from .graph import build_graph, collect_artifacts, registry  # noqa: E402

log = logging.getLogger("wikipedia-agent")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="wikipedia-agent")
graph = build_graph()
app.mount("/artifacts", StaticFiles(directory=config.ARTIFACTS_DIR), name="artifacts")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None


class ChatResponse(BaseModel):
    thread_id: str
    answer: str
    artifacts: list[str]
    tool_calls: list[dict]
    usage: dict
    seconds: float


@app.get("/healthz")
def healthz():
    return {"status": "ok", "model": config.LLM_MODEL, "skills": list(registry.skills)}


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    thread_id = req.thread_id or uuid.uuid4().hex
    cfg = {"configurable": {"thread_id": thread_id}, "recursion_limit": config.MAX_STEPS * 2}
    before = len(graph.get_state(cfg).values.get("messages", []))
    t0 = time.monotonic()
    try:
        state = graph.invoke({"messages": [HumanMessage(req.message)]}, cfg)
    except Exception as exc:
        log.exception("agent failed")
        raise HTTPException(502, f"agent failed: {type(exc).__name__}: {exc}") from exc
    new = state["messages"][before:]
    calls = [{"name": c["name"], "args": c["args"]} for m in new for c in (getattr(m, "tool_calls", None) or [])]
    usage = {"input_tokens": 0, "output_tokens": 0, "model_calls": 0}
    for m in new:
        if u := getattr(m, "usage_metadata", None):
            usage["input_tokens"] += u.get("input_tokens", 0)
            usage["output_tokens"] += u.get("output_tokens", 0)
            usage["model_calls"] += 1
    seconds = round(time.monotonic() - t0, 1)
    log.info("thread=%s calls=%d tokens=%s seconds=%s", thread_id, len(calls), usage, seconds)
    return ChatResponse(thread_id=thread_id, answer=new[-1].content, artifacts=collect_artifacts(new),
                        tool_calls=calls, usage=usage, seconds=seconds)


@app.get("/", response_class=HTMLResponse)
def index():
    return (Path(__file__).parent / "static" / "index.html").read_text(encoding="utf-8")
