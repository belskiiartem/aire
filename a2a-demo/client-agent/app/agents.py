import httpx
import os

AGENT_1_URL = os.getenv("AGENT_1_URL", "http://a2a-demo-server:8080")


def call_agent_1(message: str):
    response = httpx.post(
        f"{AGENT_1_URL}/chat",
        json={"message": message},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()


# ---------------------------
# A2A Agent (Coordinator)
# ---------------------------
def a2a_agent(state):
    user_input = state["input"]

    result = call_agent_1(user_input)

    return {
        "final_answer": f"""
[Agent-2]

Delegated to Agent-1:

{result.get("response")}
"""
    }