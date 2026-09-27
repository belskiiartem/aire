"""LangGraph agent: one model node, one tool node, conversation memory per thread."""
from __future__ import annotations

import json
import os
from datetime import date

from langchain_core.messages import SystemMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from . import config
from .skills import SkillRegistry

registry = SkillRegistry(config.SKILLS_DIR)
config.ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
SKILL_ENV = {
    "WIKI_INTEREST_OUTPUT": str(config.ARTIFACTS_DIR),
    "WIKI_INTEREST_CACHE": os.getenv("WIKI_INTEREST_CACHE", str(config.WORK_DIR / "cache")),
}


def _public_paths(text: str) -> str:
    # Absolute container paths are meaningless to the user and cost tokens; expose them as API-relative URLs.
    return text.replace(str(config.ARTIFACTS_DIR), "artifacts")


@tool
def load_skill(name: str) -> str:
    """Load the full instructions (SKILL.md) of an installed skill. Call before using a skill for the first time."""
    try:
        return registry.get(name).body
    except KeyError as exc:
        return str(exc)


@tool
def read_skill_file(skill: str, path: str) -> str:
    """Read a reference file bundled with a skill, e.g. path='references/methodology.md'."""
    try:
        return registry.read_file(skill, path)
    except (KeyError, ValueError) as exc:
        return f"error: {exc}"


@tool
def run_skill_command(skill: str, command: str) -> str:
    """Run a command from a skill's instructions, written exactly as in SKILL.md, e.g.
    skill='wikipedia-interest', command='python scripts/wiki-interest analyze --topic "Astronomy" --languages uk'.
    Returns the command's JSON output."""
    try:
        out = registry.run_command(skill, command, SKILL_ENV, config.TOOL_TIMEOUT_S, config.TOOL_OUTPUT_LIMIT)
    except (KeyError, ValueError) as exc:
        return f"error: {exc}"
    except Exception as exc:  # timeout etc. - the model should see it and recover
        return f"error: {type(exc).__name__}: {exc}"
    return _public_paths(out)


PRELOAD = config.PRELOAD_SKILLS == "all" or (config.PRELOAD_SKILLS == "auto" and len(registry.skills) == 1)
# Fewer tools = fewer wrong choices for small models: no load_skill when instructions are already inlined.
TOOLS = [read_skill_file, run_skill_command] if PRELOAD else [load_skill, read_skill_file, run_skill_command]


def system_prompt() -> str:
    preload = PRELOAD
    parts = [
        "You are a market-research assistant for founders of B2C apps. You answer with evidence from tools, "
        "never from memory, and you make assumptions and limitations explicit.",
        f"Today is {date.today():%Y-%m-%d}.",
        "Reply in the language the user writes in. Keep answers short and scannable (tables, bullets).",
        "Artifacts such as report.pdf are served to the user at the relative URLs the tools return "
        "(e.g. artifacts/<run_id>/report.pdf); include them as markdown links.",
        "If a request is ambiguous (unknown topic meaning, unclear languages), make a reasonable assumption, "
        "state it, and proceed; the user can refine it afterwards.",
        "Installed skills:\n" + registry.catalogue(),
    ]
    if preload:
        for s in registry.skills.values():
            parts.append(f"<skill name=\"{s.name}\">\n{s.body}\n</skill>")
    else:
        parts.append("Call load_skill before using a skill.")
    return "\n\n".join(parts)


def build_graph(model: str | None = None, checkpointer=None):
    llm = ChatOpenAI(model=model or config.LLM_MODEL, base_url=config.LLM_BASE_URL, api_key=config.LLM_API_KEY,
                     temperature=config.LLM_TEMPERATURE, timeout=120, max_retries=2)
    # One analyze call already covers every language; parallel calls from small models were exact duplicates.
    llm_tools = llm.bind_tools(TOOLS, parallel_tool_calls=False)
    sys_msg = SystemMessage(system_prompt())

    def agent(state: MessagesState):
        return {"messages": [llm_tools.invoke([sys_msg, *state["messages"]])]}

    g = StateGraph(MessagesState)
    g.add_node("agent", agent)
    g.add_node("tools", ToolNode(TOOLS))
    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition)
    g.add_edge("tools", "agent")
    return g.compile(checkpointer=checkpointer if checkpointer is not None else InMemorySaver())


def collect_artifacts(messages) -> list[str]:
    """Artifact URLs mentioned in tool results of this turn (for clients that render downloads)."""
    found: list[str] = []
    for m in messages:
        if getattr(m, "type", "") != "tool":
            continue
        try:
            data = json.loads(m.content)
        except (TypeError, ValueError):
            continue
        arts = data.get("artifacts", {}) if isinstance(data, dict) else {}
        if isinstance(data, dict) and "pdf" in data and isinstance(data["pdf"], str):
            arts = {**arts, "pdf": data["pdf"]}
        for v in arts.values():
            if isinstance(v, str) and v.startswith("artifacts/") and v not in found:
                found.append(v)
    return found
