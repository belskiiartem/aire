resource "kubectl_manifest" "openAiSecret-agentgateway" {
  yaml_body  = file("secrets/openAIkey.yaml")
}

resource "kubectl_manifest" "openAiSecret-kagent" {
  yaml_body          = file("secrets/openAIkey.yaml")
  override_namespace = "kagent"
}

# agentgateway reads the provider key from the namespace of the AgentgatewayBackend.
# The namespace is created by Flux (releases/wikipedia-agent.yaml), so apply after the first reconcile.
resource "kubectl_manifest" "openAiSecret-wikipedia-agent" {
  yaml_body          = file("secrets/openAIkey.yaml")
  override_namespace = "wikipedia-agent"
}
