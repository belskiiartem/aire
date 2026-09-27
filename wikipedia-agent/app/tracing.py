"""Phoenix (OpenInference) tracing, shared by both entrypoints.

Enabled when PHOENIX_COLLECTOR_ENDPOINT is set; PHOENIX_API_KEY is read from the environment by phoenix.otel.
Traces show every model call and every skill command with inputs, outputs, token counts and latency.
"""
from __future__ import annotations

import logging

from . import config

log = logging.getLogger(__name__)


def setup() -> bool:
    if not config.PHOENIX_COLLECTOR_ENDPOINT:
        return False
    from openinference.instrumentation.langchain import LangChainInstrumentor
    from phoenix.otel import register

    provider = register(project_name=config.PHOENIX_PROJECT,
                        endpoint=config.PHOENIX_COLLECTOR_ENDPOINT.rstrip("/") + "/v1/traces",
                        batch=True, set_global_tracer_provider=True)
    LangChainInstrumentor().instrument(tracer_provider=provider)
    log.info("Phoenix tracing -> %s (project %s)", config.PHOENIX_COLLECTOR_ENDPOINT, config.PHOENIX_PROJECT)
    return True
