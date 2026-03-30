from langgraph.graph import StateGraph
from app.schemas import AgentState
from app.agents import coordinator, logs_agent, metrics_agent, aggregator

graph = StateGraph(AgentState)

graph.add_node("coordinator", coordinator)
graph.add_node("logs", logs_agent)
graph.add_node("metrics", metrics_agent)
graph.add_node("aggregator", aggregator)

graph.set_entry_point("coordinator")

def route_decision(state):
    return state["route"]

graph.add_conditional_edges("coordinator", route_decision)

graph.add_edge("logs", "aggregator")
graph.add_edge("metrics", "aggregator")

app_graph = graph.compile()