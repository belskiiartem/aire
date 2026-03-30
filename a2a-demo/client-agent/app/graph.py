from langgraph.graph import StateGraph
from app.schemas import AgentState
from app.agents import a2a_agent

graph = StateGraph(AgentState)

graph.add_node("a2a", a2a_agent)
graph.set_entry_point("a2a")

app_graph = graph.compile()