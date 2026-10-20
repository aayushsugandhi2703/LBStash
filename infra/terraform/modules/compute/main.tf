# Server (AWS: EC2)
# One Ubuntu VM with a public IP, set up on first boot by cloud-init.yaml.

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

# Data centres in the region (Mumbai has one)
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# Latest Ubuntu image that fits the chosen VM type
data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = "Canonical Ubuntu"
  operating_system_version = var.ubuntu_version
  shape                    = var.shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

# ---------------------------------------------------------------
# The VM
# ---------------------------------------------------------------

resource "oci_core_instance" "this" {
  compartment_id      = var.compartment_ocid
  availability_domain = data.oci_identity_availability_domains.ads.availability_domains[var.availability_domain_index].name
  display_name        = "${var.name}-vm"
  shape               = var.shape

  # CPU and RAM: only Flex shapes let you choose
  dynamic "shape_config" {
    for_each = endswith(var.shape, "Flex") ? [1] : []
    content {
      ocpus         = var.ocpus
      memory_in_gbs = var.memory_gb
    }
  }

  # Operating system and disk
  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  # Network card: public subnet, public IP, firewall
  create_vnic_details {
    subnet_id        = var.subnet_id
    assign_public_ip = true # one public IP, free while the VM exists
    nsg_ids          = var.nsg_ids
    hostname_label   = var.name
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key                                   # who may log in
    user_data           = base64encode(file("${path.module}/cloud-init.yaml")) # first-boot setup
  }

  # Delete the disk together with the VM, so no paid leftovers stay behind
  preserve_boot_volume = false

  lifecycle {
    # A newer Ubuntu image appearing later must not rebuild a running server
    ignore_changes = [source_details[0].source_id]
  }
}
