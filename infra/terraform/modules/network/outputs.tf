# ---------------------------------------------------------------
# Used by other modules
# ---------------------------------------------------------------

output "vcn_id" {
  description = "ID of the network (used by the nsg module)."
  value       = oci_core_vcn.this.id
}

output "public_subnet_id" {
  description = "ID of the public subnet (used by the compute module)."
  value       = oci_core_subnet.public.id
}
