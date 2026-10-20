# Backup storage (AWS: S3)
# One private bucket for database backups. Always Free gives 20 GB.

terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

# ---------------------------------------------------------------
# Lookups (nothing is created here)
# ---------------------------------------------------------------

# Every tenancy has one fixed storage namespace
data "oci_objectstorage_namespace" "this" {
  compartment_id = var.compartment_ocid
}

# ---------------------------------------------------------------
# The bucket
# ---------------------------------------------------------------

resource "oci_objectstorage_bucket" "backups" {
  compartment_id = var.compartment_ocid
  namespace      = data.oci_objectstorage_namespace.this.namespace
  name           = var.bucket_name
  access_type    = "NoPublicAccess" # private: no one can read it without permission
  storage_tier   = "Standard"
  versioning     = "Disabled"
}
