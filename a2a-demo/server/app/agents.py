import json
import re
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# ---------------------------
# Utils
# ---------------------------
def extract_json(text: str):
    """Safe JSON extraction from LLM output"""
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise ValueError(f"Invalid JSON from LLM: {text}")


# ---------------------------
# Coordinator (LLM reasoning)
# ---------------------------
def coordinator(state):
    prompt = f"""
You are a coordinator agent.

User request: {state["input"]}

Decide which agents to call:
- logs
- metrics

IMPORTANT:
- Return ONLY valid JSON
- No extra text

Format:
{{
  "route": ["logs"] | ["metrics"] | ["logs", "metrics"],
  "reason": "short explanation"
}}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    content = response.choices[0].message.content
    print("COORDINATOR RAW:", content)

    decision = extract_json(content)

    return {
        "route": decision["route"],
        "reason": decision["reason"]
    }


# ---------------------------
# Logs Agent (LLM)
# ---------------------------
def logs_agent(state):
    prompt = f"""
You are a logs analysis agent.

Analyze logs for the following issue:
{state["input"]}

Provide short diagnosis.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.choices[0].message.content
    print("LOGS RAW:", result)

    return {
        "logs_result": result
    }


# ---------------------------
# Metrics Agent (LLM)
# ---------------------------
def metrics_agent(state):
    prompt = f"""
You are a metrics analysis agent.

Analyze system performance for:
{state["input"]}

Provide short insight.
"""

    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.choices[0].message.content
    print("METRICS RAW:", result)

    return {
        "metrics_result": result
    }


# ---------------------------
# Aggregator (LLM reasoning)
# ---------------------------
def aggregator(state):
    prompt = f"""
You are an expert SRE.

User issue:
{state["input"]}

Logs analysis:
{state.get("logs_result")}

Metrics analysis:
{state.get("metrics_result")}

Provide:
- root cause
- recommendation
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    result = response.choices[0].message.content
    print("AGGREGATOR RAW:", result)

    return {
        "final_answer": result
    }