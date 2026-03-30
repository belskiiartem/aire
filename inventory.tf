#install crds
data "http" "inventory_crds_crds" {
  for_each = toset(var.inventory_crds)
  url      = "${var.inventory_crds_url}${each.value}"
}

resource "kubectl_manifest" "inventory_crds_crds" {
  for_each  = data.http.inventory_crds_crds
  yaml_body = each.value.response_body
}

#helm install agentregistry-inventory ./charts/agentregistry -n agentregistry --create-namespace
resource "helm_release" "app" {
  name       = "agentregistry-inventory"
  namespace  = "agentregistry"
  create_namespace = true
  repository = "oci://ghcr.io/den-vasyliev/charts"
  chart      = "agentregistry"
  set = [
   {
    name  = "image.tag"
    value = "latest"
  }
  ]
}