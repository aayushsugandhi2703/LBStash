# ---------------------------------------------------------------
# Used by other modules
# ---------------------------------------------------------------

output "bucket_name" {
  description = "Name of the bucket."
  value       = oci_objectstorage_bucket.backups.name
}
