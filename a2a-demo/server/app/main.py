from fastapi import FastAPI
from pydantic import BaseModel
from phoenix.otel import register

tracer_provider = register(project_name="default")
tracer = tracer_provider.get_tracer(__name__)

app = FastAPI()

class ChatRequest(BaseModel):
    message: str


def run_agent(agent_name: str, role: str, model: str, input_text: str):
    with tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("agent.role", role)
        span.set_attribute("agent.model", model)
        span.set_attribute("agent.input", input_text)

        # do the actual work here
        result = {"output": f"{agent_name} processed: {input_text}"}

        span.set_attribute("agent.status", "ok")
        return result


@app.post("/chat")
def chat(req: ChatRequest):
    with tracer.start_as_current_span("chat.request") as span:
        span.set_attribute("request.type", "chat")
        span.set_attribute("input.message", req.message)

        logs_result = run_agent(
            agent_name="logs_agent",
            role="logs-analysis",
            model="gpt-4o-mini",
            input_text=req.message,
        )

        metrics_result = run_agent(
            agent_name="metrics_agent",
            role="metrics-analysis",
            model="gpt-4.1-nano",
            input_text=req.message,
        )

        span.set_attribute("agents.count", 2)

        return {
            "logs_result": logs_result,
            "metrics_result": metrics_result,
        }