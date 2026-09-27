"""kagent BYO entrypoint: the same LangGraph agent served over A2A on :8080.

kagent deploys this image for an `Agent` of type BYO and injects KAGENT_URL / KAGENT_NAME / KAGENT_NAMESPACE.
Conversation state is stored in the kagent controller (KAgentCheckpointer), so it survives pod restarts.
"""
from __future__ import annotations

import httpx
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from fastapi.staticfiles import StaticFiles
from kagent.core import KAgentConfig
from kagent.langgraph import KAgentApp, KAgentCheckpointer

from . import __version__, config
from .graph import build_graph, registry

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

app = KAgentApp(graph=graph, agent_card=agent_card, config=kagent_config).build()
app.mount("/artifacts", StaticFiles(directory=config.ARTIFACTS_DIR), name="artifacts")
