# Starting point. Each module builds one part:
#   network         VCN, internet gateway, route table, subnet   (AWS: VPC)
#   nsg             firewall rules                               (AWS: security group)
#   compute         the server                                   (AWS: EC2)
#   object_storage  backup bucket                                (AWS: S3)

# ---------------------------------------------------------------
# Terraform and plugin versions
# ---------------------------------------------------------------

terraform {
  required_version = ">= 1.12"

  # State lives in an Object Storage bucket, so your Mac and GitHub Actions share it.
  # Create the bucket by hand first (see README). The namespace is an ID, not a secret.
  backend "oci" {
    bucket              = "lbstash-tfstate"
    namespace           = "bmlo47nyjjzu"
    region              = "ap-mumbai-1"
    key                 = "terraform.tfstate"
    config_file_profile = "DEFAULT"
  }

  required_providers {
    oci = {
      source  = "oracle/oci"
      version = ">= 6.0.0"
    }
  }
}

# ---------------------------------------------------------------
# Login to Oracle Cloud
# ---------------------------------------------------------------

# Reads ~/.oci/config (profile DEFAULT).
# No keys or secrets are stored in this folder.
provider "oci" {
  region              = var.region
  config_file_profile = "DEFAULT"
}

# ---------------------------------------------------------------
# 1. Network: private network with a public subnet
# ---------------------------------------------------------------

module "network" {
  source = "./modules/network"

  compartment_ocid   = var.compartment_ocid
  name               = var.name
  vcn_cidr           = var.vcn_cidr
  public_subnet_cidr = var.public_subnet_cidr
}

# ---------------------------------------------------------------
# 2. Firewall: which ports are open, and to whom
# ---------------------------------------------------------------

module "nsg" {
  source = "./modules/nsg"

  compartment_ocid  = var.compartment_ocid
  name              = var.name
  vcn_id            = module.network.vcn_id # from the network module
  web_ports         = var.web_ports
  web_ingress_cidrs = var.web_ingress_cidrs
  ssh_ingress_cidrs = var.ssh_ingress_cidrs
}

# ---------------------------------------------------------------
# 3. Server: placed in the public subnet, behind the firewall
# ---------------------------------------------------------------

module "compute" {
  source = "./modules/compute"

  tenancy_ocid              = var.tenancy_ocid
  compartment_ocid          = var.compartment_ocid
  name                      = var.name
  subnet_id                 = module.network.public_subnet_id # from the network module
  nsg_ids                   = [module.nsg.nsg_id]             # from the nsg module
  shape                     = var.shape
  ocpus                     = var.ocpus
  memory_gb                 = var.memory_gb
  boot_volume_gb            = var.boot_volume_gb
  ubuntu_version            = var.ubuntu_version
  availability_domain_index = var.availability_domain_index
  ssh_public_key            = join("\n", concat([trimspace(file(pathexpand(var.ssh_public_key_path)))], var.extra_ssh_public_keys))
}

# ---------------------------------------------------------------
# 4. Backups: private bucket
# ---------------------------------------------------------------

module "object_storage" {
  source = "./modules/object_storage"

  compartment_ocid = var.compartment_ocid
  bucket_name      = var.backup_bucket_name
}
