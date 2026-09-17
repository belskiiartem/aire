
resource "helm_release" "phoenix" {
  name       = "phoenix"
  namespace  = "phoenix"
  create_namespace = true

  repository = "oci://registry-1.docker.io/arizephoenix"
  chart      = "phoenix-helm"

  version    = "12.0.10"

  values = [
    yamlencode({
        env = {
        PHOENIX_ENABLE_AUTH = "false"
        }
    })
    ]
}