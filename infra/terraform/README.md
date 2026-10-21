# Terraform (Oracle Cloud)

Builds the server for LBStash in Mumbai, inside the `LBStash` compartment. The first 30 days run on the trial credit; after that move to the free ARM VM (see the server setup guide).

Login comes from `~/.oci/config`. No secrets live in this folder.

## What it builds

| OCI service | Creates | AWS name |
|---|---|---|
| Networking | VCN, internet gateway, route table, public subnet | VPC |
| Networking | Firewall (NSG): ports 22, 80, 443 | Security group |
| Compute | AMD VM (E5.Flex, 1 OCPU = 2 vCPU, 4 GB), Ubuntu 24.04, public IP | EC2 |
| Block Volume | 100 GB boot disk | EBS |
| Object Storage | Private bucket `lbstash-backups` | S3 |

On first boot the VM installs Docker, fail2ban and its own firewall, and turns off SSH passwords.

Done by hand, not by Terraform: the Terraform user and the VM's permissions (`policies.txt`), and the state bucket `lbstash-tfstate`.

## Folders

```
infra/terraform/
├── main.tf, variables.tf, outputs.tf
├── terraform.tfvars          your values (git-ignored)
├── policies.txt              permissions to create in the console
└── modules/
    ├── network/              VCN, gateway, route table, subnet
    ├── nsg/                  firewall rules
    ├── compute/              the VM + cloud-init.yaml (first-boot setup)
    └── object_storage/       backup bucket
```

## Run it

Easiest: GitHub > Actions > **Terraform** > Run workflow. Secrets: [Secrets](../../docs/infrastructure/SECRETS.md). Steps: [Server setup](../../docs/infrastructure/SERVER_SETUP.md).

From your Mac:

```bash
cp terraform.tfvars.example terraform.tfvars   # fill in the two OCIDs
terraform init
terraform plan
terraform apply
```

If you also run it on GitHub, keep `extra_ssh_public_keys` the same in both places.

Delete everything: `terraform destroy`.
