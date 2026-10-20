# ---------------------------------------------------------------
# Where and what to call it
# ---------------------------------------------------------------

variable "tenancy_ocid" {
  description = "Your Oracle account ID. Used to look up availability domains."
  type        = string
}

variable "compartment_ocid" {
  description = "Compartment to build in."
  type        = string
}

variable "name" {
  description = "Prefix added to every resource name."
  type        = string
}

variable "availability_domain_index" {
  description = "Which data centre in the region."
  type        = number
}

# ---------------------------------------------------------------
# Network
# ---------------------------------------------------------------

variable "subnet_id" {
  description = "Subnet to place the VM in."
  type        = string
}

variable "nsg_ids" {
  description = "Firewalls to attach to the VM."
  type        = list(string)
}

# ---------------------------------------------------------------
# Size
# ---------------------------------------------------------------

variable "shape" {
  description = "VM type."
  type        = string
}

variable "ocpus" {
  description = "CPUs (Flex shapes only)."
  type        = number
}

variable "memory_gb" {
  description = "RAM in GB (Flex shapes only)."
  type        = number
}

variable "boot_volume_gb" {
  description = "Disk size in GB."
  type        = number
}

# ---------------------------------------------------------------
# Operating system and login
# ---------------------------------------------------------------

variable "ubuntu_version" {
  description = "Ubuntu release to install."
  type        = string
}

variable "ssh_public_key" {
  description = "The public key text itself, not a file path."
  type        = string
}
