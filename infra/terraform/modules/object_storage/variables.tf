# ---------------------------------------------------------------
# Where and what to call it
# ---------------------------------------------------------------

variable "compartment_ocid" {
  description = "Compartment to build in."
  type        = string
}

variable "bucket_name" {
  description = "Name of the bucket."
  type        = string
}
