from fastapi import FastAPI
from pydantic import BaseModel
from app.graph import app_graph
from phoenix.otel import register

tracer_provider = register(
  project_name="default",
)

tracer = tracer_provider.get_tracer(__name__)

app = FastAPI()

class ChatRequest(BaseModel):
    message: str

@app.get("/.well-known/agent.json")
def agent_card():
    return {
        "name": "LangGraph Multi-Agent",
        "framework": "langgraph",
        "capabilities": [
            "multi-agent",
            "reasoning",
            "logs-analysis",
            "metrics-analysis"
        ],
        "endpoints": {
            "chat": "/chat"
        }
    }

@tracer.chain
@app.post("/chat")
def chat(req: ChatRequest):
    result = app_graph.invoke({
        "input": req.message
    })
    return {
        "response": result.get("final_answer"),
        "reason": result.get("reason")
    }