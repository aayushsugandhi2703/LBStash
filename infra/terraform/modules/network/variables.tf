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

# ---------------------------------------------------------------
# Address ranges
# ---------------------------------------------------------------

variable "vcn_cidr" {
  description = "Address range of the whole network."
  type        = string
}

variable "public_subnet_cidr" {
  description = "Address range of the public subnet."
  type        = string
}
