terraform {
  backend "local" {
    path = "terraform.tfstate"
  }

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "= 3.0.1"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "= 3.1.1"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.19"
    }
    kustomization = {
      source  = "kbst/kustomization"
      version = "~> 0.9.7"
    }
  }

}
