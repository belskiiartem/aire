resource "helm_release" "qdrant" {
  name             = "qdrant"
  namespace        = "qdrant"
  create_namespace = true

  repository = "https://qdrant.github.io/qdrant-helm"
  chart      = "qdrant"
  version    = "1.17.1"

}