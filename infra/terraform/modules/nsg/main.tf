# Firewall (AWS: security group)
# A Network Security Group (NSG) is a list of allowed incoming traffic. Anything not listed is blocked.

terraform {
  required_providers {
    oci = {
      source = "oracle/oci"
    }
  }
}

# One rule for every combination of address range and web port
locals {
  web_rules = {
    for pair in setproduct(var.web_ingress_cidrs, var.web_ports) :
    "${pair[0]}-${pair[1]}" => { cidr = pair[0], port = pair[1] }
  }
}

# ---------------------------------------------------------------
# The firewall
# ---------------------------------------------------------------

resource "oci_core_network_security_group" "this" {
  compartment_id = var.compartment_ocid
  vcn_id         = var.vcn_id
  display_name   = "${var.name}-vm-nsg"
}

# ---------------------------------------------------------------
# Allowed incoming traffic
# ---------------------------------------------------------------

# Website: ports 80 and 443 (http and https)
resource "oci_core_network_security_group_security_rule" "web" {
  for_each = local.web_rules

  network_security_group_id = oci_core_network_security_group.this.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source                    = each.value.cidr
  source_type               = "CIDR_BLOCK"
  description               = "web ${each.value.port}"

  tcp_options {
    destination_port_range {
      min = each.value.port
      max = each.value.port
    }
  }
}

# SSH: port 22. Only your key works, because the password login is off (see compute/cloud-init.yaml).
resource "oci_core_network_security_group_security_rule" "ssh" {
  for_each = toset(var.ssh_ingress_cidrs)

  network_security_group_id = oci_core_network_security_group.this.id
  direction                 = "INGRESS"
  protocol                  = "6" # TCP
  source                    = each.value
  source_type               = "CIDR_BLOCK"
  description               = "ssh"

  tcp_options {
    destination_port_range {
      min = 22
      max = 22
    }
  }
}

# Ping-style message that stops big packets from getting stuck
resource "oci_core_network_security_group_security_rule" "icmp_path_mtu" {
  network_security_group_id = oci_core_network_security_group.this.id
  direction                 = "INGRESS"
  protocol                  = "1" # ICMP
  source                    = "0.0.0.0/0"
  source_type               = "CIDR_BLOCK"
  description               = "path MTU discovery"

  icmp_options {
    type = 3
    code = 4
  }
}
