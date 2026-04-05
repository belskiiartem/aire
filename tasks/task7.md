# How could we handle 'agent got stuck' scenarios?
The health check should be realised on the Agent level. The status of the heals check can be monitored in the agentregistry-inventory

# Any automatic timeout/circuit breaker patterns coming out form this framework ?
We can limit the number of requests in the AgentgatewayPolicy
  traffic:
    rateLimit:
      requestsPerMinute: N

The timeouts can be configured in the MCP servers
https://github.com/belskiiartem/aire/blob/main/releases/mcp/echo-mcp-server.yaml#L8

# How does kgateway handle model failover?
We can have a list of models\providers in the backend group (AgentgatewayBackend)
In case the model with higher priority is unavailable, kgateway will try to use the next one from the list.
https://agentgateway.dev/docs/kubernetes/latest/llm/failover/

# Can we automatically switch from OpenAI to Claude to local model ?
We can call abstraction from the ModelRoute, like default-agent-model. In that way, we can change the model to any we want on the infrastructure side.

# Could we seamlessly handle the response formats form these providers?
We can configure output with Prompt Enrichment
https://agentgateway.dev/docs/kubernetes/latest/tutorials/prompt-enrichment/

# Can we version the agents built form kagent?
We can pack the agent into a Docker or OCI image and deploy it with a specific tag

# Any blue/green or canary deployment patterns for agents?
The agent is a Kubernetes object, so we can deploy it as a regular deployment that we have

# What's the fastmcp-python framework mentioned?
I don't have it in the infrastructure yet.

# Is it the easiest path to mcp?
Can't answer right now.

# About finops: how much control I can have?
I can control the bill in the Phoenix

# Token level / per agent level
can be tracked by agentgateway or phenix
https://agentgateway.dev/docs/kubernetes/main/llm/cost-tracking/

# Can I implement custom cost controls?
# Per-agent budgets or depth of Token limits
I don't have it in current realisation yet. Can be realised on the backend side.

# vLLM suitable for agents with many back and forth tool calls, or is it better for single shot inference?
It is better for a single-shot interface. (didn't try yet)

# llm-d's scheduler - helps when agents makes 15 llms calls?
Yes, llm-d can queue requests, prioritise it provide retries capabilities