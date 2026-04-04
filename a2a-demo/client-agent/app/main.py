from fastapi import FastAPI
from pydantic import BaseModel
from app.graph import app_graph
import os
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
@tracer.chain
def chat(req: ChatRequest):
    result = app_graph.invoke({
        "input": req.message
    }, timeout=120)
    return {
        "response": result.get("final_answer"),
        "reason": result.get("reason")
    }