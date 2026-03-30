variable "oci_registry" {
  type = string
}

variable "releases_version" {
  type = string
}

variable "inventory_crds" {
  type = list(string)
}

variable "inventory_crds_url" {
  type = string
}