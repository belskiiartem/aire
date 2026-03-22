resource "kubectl_manifest" "openAiSecret-agentgateway" {
  yaml_body  = file("secrets/openAIkey.yaml")
}

resource "kubectl_manifest" "openAiSecret-kagent" {
  yaml_body          = file("secrets/openAIkey.yaml")
  override_namespace = "kagent"
}