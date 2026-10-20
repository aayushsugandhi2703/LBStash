# ---------------------------------------------------------------
# Identity
# ---------------------------------------------------------------

output "instance_id" {
  description = "ID of the server."
  value       = oci_core_instance.this.id
}

# ---------------------------------------------------------------
# Addresses
# ---------------------------------------------------------------

output "public_ip" {
  description = "Address on the internet."
  value       = oci_core_instance.this.public_ip
}

output "private_ip" {
  description = "Address inside the network."
  value       = oci_core_instance.this.private_ip
}
