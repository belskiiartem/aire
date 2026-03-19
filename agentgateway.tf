# agentgateway
# https://agentgateway.dev/docs/kubernetes/latest/quickstart/install/
#

locals {
  gateway_api_version = "release-1.5"
  gateway_api_crds = ["gateway.networking.k8s.io_backendtlspolicies.yaml",
    "gateway.networking.k8s.io_gatewayclasses.yaml",
    "gateway.networking.k8s.io_gateways.yaml",
    "gateway.networking.k8s.io_httproutes.yaml",
    "gateway.networking.k8s.io_listenersets.yaml",
    "gateway.networking.k8s.io_referencegrants.yaml",
    "gateway.networking.k8s.io_tlsroutes.yaml",
    "gateway.networking.k8s.io_grpcroutes.yaml",
  "gateway.networking.k8s.io_vap_safeupgrades.yaml"]

  gateway_api_crds_url = "https://raw.githubusercontent.com/kubernetes-sigs/gateway-api/refs/heads/${local.gateway_api_version}/config/crd/standard/"

}

data "http" "gateway_api_crds" {
  for_each = toset(local.gateway_api_crds)
  url      = "${local.gateway_api_crds_url}${each.value}"
}

resource "kubectl_manifest" "gateway_api_crds" {
  for_each  = data.http.gateway_api_crds
  yaml_body = each.value.response_body
}

# -------------------------------
# CRDs Helm chart
# -------------------------------
resource "helm_release" "agentgateway_crds" {
  name             = "agentgateway-crds"
  repository       = "oci://cr.agentgateway.dev/charts"
  chart            = "agentgateway-crds"
  namespace        = "agentgateway-system"
  create_namespace = true

  depends_on = [
    kubectl_manifest.gateway_api_crds
  ]
}

resource "helm_release" "agentgateway" {
  name       = "agentgateway"
  repository = "oci://cr.agentgateway.dev/charts"
  chart      = "agentgateway"
  namespace  = "agentgateway-system"

  depends_on = [
    helm_release.agentgateway_crds
  ]
}

# LLM https://agentgateway.dev/docs/kubernetes/latest/quickstart/llm/
resource "kubectl_manifest" "openAiSecret" {
  yaml_body  = file("secrets/openAIkey.yaml")
  depends_on = [helm_release.agentgateway]
}

resource "kubectl_manifest" "agentgatewayBackend" {
  yaml_body  = file("config/AgentGateway/AgentgatewayBackend.yaml")
  depends_on = [helm_release.agentgateway]
}

resource "kubectl_manifest" "gateway" {
  yaml_body  = file("config/AgentGateway/Gateway.yaml")
  depends_on = [helm_release.agentgateway]
}

resource "kubectl_manifest" "route" {
  yaml_body  = file("config/AgentGateway/HTTPRoute.yaml")
  depends_on = [helm_release.agentgateway]
}


#kagent
resource "kubernetes_namespace_v1" "kagent" {
  metadata {
    name = "kagent"
  }
}

resource "kubectl_manifest" "openAiSecret-kagent" {
  yaml_body          = file("secrets/openAIkey.yaml")
  override_namespace = "kagent"
  depends_on         = [kubernetes_namespace_v1.kagent]
}


resource "helm_release" "kagent-crds" {
  name       = "kagent-crds"
  repository = "oci://ghcr.io/kagent-dev/kagent/helm"
  chart      = "kagent-crds"
  namespace  = "kagent"

  depends_on = [
    helm_release.agentgateway_crds,
    kubectl_manifest.openAiSecret-kagent
  ]
}

resource "helm_release" "kagent" {
  name       = "kagent"
  repository = "oci://ghcr.io/kagent-dev/kagent/helm"
  chart      = "kagent"
  namespace  = "kagent"
  timeout    = 600
  set = [
    {
      name  = "providers.default"
      value = "openAI"
    },
    {
      name  = "providers.openAI.model"
      value = "gpt-4.1-nano"
    },
    {
      name  = "providers.openAI.apiKeySecretRef"
      value = "openai-api-key"
    },
    {
      name  = "providers.openAI.apiKeySecretKey"
      value = "Authorization"
    }
  ]

  depends_on = [
    helm_release.kagent-crds
  ]
}