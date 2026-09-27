import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Any OpenAI-compatible endpoint. In the cluster this is agentgateway, which holds the provider key.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or "not-needed-behind-gateway"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0"))

# Where users reach /artifacts (e.g. http://gateway/wikipedia-agent). Empty = relative links, fine for the built-in UI.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

SKILLS_DIR = Path(os.getenv("SKILLS_DIR", ROOT / "skills"))
WORK_DIR = Path(os.getenv("WORK_DIR", ROOT / "work"))
ARTIFACTS_DIR = WORK_DIR / "artifacts"

# "auto" inlines SKILL.md when only one skill is installed: saves a model round trip.
PRELOAD_SKILLS = os.getenv("PRELOAD_SKILLS", "auto")
MAX_STEPS = int(os.getenv("MAX_STEPS", "24"))
TOOL_TIMEOUT_S = int(os.getenv("TOOL_TIMEOUT_S", "240"))
TOOL_OUTPUT_LIMIT = int(os.getenv("TOOL_OUTPUT_LIMIT", "12000"))

PHOENIX_COLLECTOR_ENDPOINT = os.getenv("PHOENIX_COLLECTOR_ENDPOINT")
PHOENIX_PROJECT = os.getenv("PHOENIX_PROJECT", "wikipedia-agent")
