# ---------------------------------------------------------------
# Where and what to call it
# ---------------------------------------------------------------

variable "compartment_ocid" {
  description = "Compartment to build in."
  type        = string
}

variable "name" {
  description = "Prefix added to every resource name."
  type        = string
}

variable "vcn_id" {
  description = "Network this firewall belongs to."
  type        = string
}

# ---------------------------------------------------------------
# Website access
# ---------------------------------------------------------------

variable "web_ports" {
  description = "Ports open for the website."
  type        = list(number)
}

variable "web_ingress_cidrs" {
  description = "Who can reach the website. [] opens nothing."
  type        = list(string)
}

# ---------------------------------------------------------------
# SSH access
# ---------------------------------------------------------------

variable "ssh_ingress_cidrs" {
  description = "Who can reach SSH (port 22)."
  type        = list(string)
}
