from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from app.graph import app_graph
import os
import time
import httpx
from phoenix.otel import register

tracer_provider = register(
  project_name="default",
)

tracer = tracer_provider.get_tracer(__name__)

app = FastAPI()

AGENT_1_URL = os.getenv("AGENT_1_URL", "http://agent-1:8080")

class ChatRequest(BaseModel):
    message: str

@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "name": "Agent-2 (A2A Proxy)",
        "description": "Delegates requests to Agent-1",
        "capabilities": [
            "agent-to-agent",
            "delegation"
        ],
        "connections": [
            {
                "type": "a2a",
                "target": "agent-1",
                "endpoint": f"{AGENT_1_URL}/chat"
            }
        ]
    }

@app.post("/chat")
def chat(req: ChatRequest):
    with tracer.start_as_current_span("chat.request") as span:
        span.set_attribute("request.type", "chat")
        span.set_attribute("input.message", req.message)
        span.set_attribute("agent.target", "agent-1")
        span.set_attribute("http.url", f"{AGENT_1_URL}/chat")
        span.set_attribute("http.method", "POST")

        payload = {"message": req.message}
        start_time = time.perf_counter()

        try:
            with tracer.start_as_current_span("http.post.agent1") as http_span:
                http_span.set_attribute("http.url", f"{AGENT_1_URL}/chat")
                http_span.set_attribute("http.method", "POST")
                http_span.set_attribute("peer.service", "agent-1")

                response = httpx.post(f"{AGENT_1_URL}/chat", json=payload, timeout=120)

                elapsed_ms = (time.perf_counter() - start_time) * 1000
                http_span.set_attribute("http.status_code", response.status_code)
                http_span.set_attribute("http.duration_ms", elapsed_ms)

                response.raise_for_status()
                data = response.json()

        except httpx.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            span.set_attribute("http.duration_ms", elapsed_ms)
            span.set_attribute("error", True)
            span.set_attribute("error.message", str(exc))
            raise HTTPException(status_code=502, detail=f"Upstream agent request failed: {exc}") from exc

        span.set_attribute("agents.count", 1)

        return {
            "response": data.get("response"),
            "reason": data.get("reason"),
        }