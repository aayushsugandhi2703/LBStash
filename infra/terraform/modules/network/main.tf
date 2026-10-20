# Network (AWS: VPC)
# Private network, its door to the internet, and one public subnet.

terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

# ---------------------------------------------------------------
# VCN: the private network
# ---------------------------------------------------------------

resource "oci_core_vcn" "this" {
  compartment_id = var.compartment_ocid
  display_name   = "${var.name}-vcn"
  cidr_blocks    = [var.vcn_cidr]
  dns_label      = var.name
}

# OCI's default rule list opens SSH to everyone. Replace it with "outgoing only".
# Incoming ports are opened by the nsg module instead.
resource "oci_core_default_security_list" "locked" {
  manage_default_resource_id = oci_core_vcn.this.default_security_list_id
  display_name               = "${var.name}-locked-default"

  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }
}

# ---------------------------------------------------------------
# Internet access: gateway + route
# ---------------------------------------------------------------

# The door between the network and the internet
resource "oci_core_internet_gateway" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name}-igw"
  enabled        = true
}

# Sends all outside traffic through that door
resource "oci_core_route_table" "public" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.this.id
  display_name   = "${var.name}-public-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.this.id
  }
}

# ---------------------------------------------------------------
# Subnet: servers here can get a public IP
# ---------------------------------------------------------------

resource "oci_core_subnet" "public" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.this.id
  display_name               = "${var.name}-public"
  cidr_block                 = var.public_subnet_cidr
  dns_label                  = "pub"
  route_table_id             = oci_core_route_table.public.id
  security_list_ids          = [oci_core_default_security_list.locked.id]
  prohibit_public_ip_on_vnic = false
}
