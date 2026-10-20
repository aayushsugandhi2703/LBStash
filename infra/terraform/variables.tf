# All settings in one place. Defaults work as they are.
# Put your own values in terraform.tfvars (see terraform.tfvars.example).

# ---------------------------------------------------------------
# Account (no default: you must set these)
# ---------------------------------------------------------------

variable "tenancy_ocid" {
  description = "Your Oracle account ID. Used to look up availability domains."
  type        = string
}

variable "compartment_ocid" {
  description = "ID of the LBStash compartment. Console: Identity & Security > Compartments > LBStash > Copy OCID."
  type        = string
}

# ---------------------------------------------------------------
# General
# ---------------------------------------------------------------

variable "region" {
  description = "Must be your home region. Always Free VMs only work there."
  type        = string
  default     = "ap-mumbai-1"
}

variable "name" {
  description = "Prefix added to every resource name."
  type        = string
  default     = "lbstash"
}

# ---------------------------------------------------------------
# Network
# ---------------------------------------------------------------

variable "vcn_cidr" {
  description = "Address range of the whole private network."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidr" {
  description = "Address range of the public subnet (inside the VCN range)."
  type        = string
  default     = "10.0.1.0/24"
}

# ---------------------------------------------------------------
# Firewall
# ---------------------------------------------------------------

variable "web_ports" {
  description = "Ports open for the website."
  type        = list(number)
  default     = [80, 443]
}

variable "web_ingress_cidrs" {
  description = "Who can reach the website. [] opens nothing (use with Cloudflare Tunnel)."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ssh_ingress_cidrs" {
  description = "Who can reach SSH (port 22). Use [\"your-ip/32\"] to allow only yourself."
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

# ---------------------------------------------------------------
# Server (VM)
# ---------------------------------------------------------------

variable "shape" {
  description = "VM type. E4.Flex = AMD, paid (covered by the 30-day trial credit). A1.Flex = ARM, free up to 2 CPU / 12 GB, often out of capacity. E2.1.Micro = free but far too small for this app."
  type        = string
  default     = "VM.Standard.E4.Flex"
}

variable "ocpus" {
  description = "CPUs (Flex shapes). On E4.Flex 1 OCPU = 2 vCPU. On A1.Flex the free total is 2."
  type        = number
  default     = 1
}

variable "memory_gb" {
  description = "RAM in GB (Flex shapes). The app needs about 3 GB. On A1.Flex the free total is 12."
  type        = number
  default     = 4
}

variable "boot_volume_gb" {
  description = "Disk size in GB (minimum 47). Free total for all disks: 200."
  type        = number
  default     = 50
}

variable "ubuntu_version" {
  description = "Ubuntu release to install."
  type        = string
  default     = "24.04"
}

variable "availability_domain_index" {
  description = "Which data centre in the region (Mumbai has one). Try another if you get 'out of host capacity'."
  type        = number
  default     = 0
}

variable "ssh_public_key_path" {
  description = "Path to your public SSH key. The private key stays on your Mac."
  type        = string
  default     = "~/.ssh/lbstash_oci.pub"
}

variable "extra_ssh_public_keys" {
  description = "More public keys allowed to log in, for example the GitHub Actions deploy key."
  type        = list(string)
  default     = []
}

# ---------------------------------------------------------------
# Backups
# ---------------------------------------------------------------

variable "backup_bucket_name" {
  description = "Name of the private backup bucket."
  type        = string
  default     = "lbstash-backups"
}
