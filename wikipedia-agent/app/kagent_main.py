"""kagent BYO entrypoint: the same LangGraph agent served over A2A on :8080.

kagent deploys this image for an `Agent` of type BYO and injects KAGENT_URL / KAGENT_NAME / KAGENT_NAMESPACE.
Conversation state is stored in the kagent controller (KAgentCheckpointer), so it survives pod restarts.
"""
from __future__ import annotations

import os

# a2a-sdk traces its internal event queues (~40 spans per request); keep Phoenix focused on the agent.
# Read at import time, so it must be set before `a2a` is imported.
os.environ.setdefault("OTEL_INSTRUMENTATION_A2A_SDK_ENABLED", "false")

import httpx  # noqa: E402
from a2a.types import AgentCapabilities, AgentCard, AgentSkill  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from kagent.core import KAgentConfig  # noqa: E402
from kagent.langgraph import KAgentApp, KAgentCheckpointer  # noqa: E402

from . import __version__, config, tracing  # noqa: E402

# Our Phoenix exporter replaces kagent's built-in OTEL setup; two global tracer providers would conflict.
phoenix = tracing.setup()

from .graph import build_graph, registry  # noqa: E402

kagent_config = KAgentConfig()
graph = build_graph(checkpointer=KAgentCheckpointer(client=httpx.AsyncClient(base_url=kagent_config.url),
                                                    app_name=kagent_config.app_name))

skill = registry.get("wikipedia-interest")
agent_card = AgentCard(
    name=kagent_config.name,
    description="Market research on Wikipedia pageviews: is interest in a topic growing, in which languages, "
                "how trustworthy is the trend; charts and one-page PDF reports.",
    url="http://localhost:8080",
    version=__version__,
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text"],
    default_output_modes=["text"],
    skills=[AgentSkill(
        id=skill.name, name="Wikipedia interest analysis", description=skill.description,
        tags=["wikipedia", "market-research", "trends"],
        examples=["Чи зростає інтерес до астрономії в україномовній Wikipedia, і наскільки цьому можна довіряти?",
                  "Compare interest in intermittent fasting in Polish and Czech Wikipedia over two years."],
    )],
)

app = KAgentApp(graph=graph, agent_card=agent_card, config=kagent_config, tracing=not phoenix).build()
app.mount("/artifacts", StaticFiles(directory=config.ARTIFACTS_DIR), name="artifacts")
