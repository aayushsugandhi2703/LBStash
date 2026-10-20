# ---------------------------------------------------------------
# Used by other modules
# ---------------------------------------------------------------

output "nsg_id" {
  description = "ID of the firewall (attached to the VM by the compute module)."
  value       = oci_core_network_security_group.this.id
}
