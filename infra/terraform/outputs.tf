# Values printed after `terraform apply`.

# ---------------------------------------------------------------
# Connect
# ---------------------------------------------------------------

output "public_ip" {
  description = "Use this as the A record of your domain."
  value       = module.compute.public_ip
}

output "ssh_command" {
  description = "Copy and run this to log in."
  value       = "ssh -i ~/.ssh/lbstash_oci ubuntu@${module.compute.public_ip}"
}

# ---------------------------------------------------------------
# Resources
# ---------------------------------------------------------------

output "instance_id" {
  description = "ID of the server."
  value       = module.compute.instance_id
}

output "backup_bucket" {
  description = "Name of the backup bucket."
  value       = module.object_storage.bucket_name
}
