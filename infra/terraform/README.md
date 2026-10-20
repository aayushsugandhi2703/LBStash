# Oracle Cloud (OCI) with Terraform

Builds the server for LBStash on Oracle Cloud, in the Mumbai region, inside the `LBStash` compartment. It fits the Always Free tier, so the expected cost is ₹0/month.

Login comes from `~/.oci/config`. No keys or secrets live in this folder.

## What gets built

| OCI service | What Terraform creates | Why | AWS name |
|---|---|---|---|
| **Networking** | VCN, internet gateway, route table, public subnet | The private network and its door to the internet | VPC |
| **Networking** | Network Security Group (firewall): ports 22, 80, 443 | Blocks everything else | Security group |
| **Compute** | One ARM VM (2 CPU, 12 GB), Ubuntu 24.04, one public IP | Runs the app in Docker | EC2 |
| **Block Volume** | 100 GB boot disk (made with the VM) | The VM's disk | EBS |
| **Object Storage** | Private bucket `lbstash-backups` | Place for database backups (no backup script yet) | S3 |

On first boot the VM installs Docker, fail2ban and its own firewall, and turns off SSH passwords (`modules/compute/cloud-init.yaml`).

State (Terraform's record of what exists) is kept in the Object Storage bucket `lbstash-tfstate`, which you create by hand once. Your Mac and GitHub Actions share it.

Not built here (done by hand, see `policies.txt`): the Terraform user and group, and the VM's permissions (IAM).

Used outside Oracle: Cloudflare (DNS and HTTPS front) and Let's Encrypt (certificate), both free.

```
Internet --> Cloudflare --> public IP --> firewall (22, 80, 443) --> VM --> Docker: nginx + app
                                                                     VM --> backup bucket
```

## Cost

Everything above is inside Always Free: ARM VM up to 2 CPU / 12 GB, 200 GB disks, 20 GB bucket, 10 TB data out. Expected bill: ₹0.

You pay only if you raise `ocpus` or `memory_gb`, go past 200 GB of disk or 20 GB of backups, or upgrade to pay-as-you-go and exceed the free limits. Set a ₹1 budget alert in the console.

## Layout

```
infra/terraform/
├── main.tf                 Terraform + login + the four modules
├── variables.tf            all settings, with defaults
├── outputs.tf              public IP, ssh command, bucket name
├── terraform.tfvars        your values (git-ignored); .example is the template
├── policies.txt            permissions to create by hand in the console
├── .terraform.lock.hcl     created by `terraform init`; commit it
└── modules/
    ├── network/            VCN, internet gateway, route table, subnet
    ├── nsg/                firewall rules
    ├── compute/            the VM; cloud-init.yaml = first-boot setup
    └── object_storage/     backup bucket
```

Every module has `main.tf` (what it builds), `variables.tf` (inputs) and `outputs.tf` (what it hands on).

## Setup (once)

1. Install Terraform: `brew tap hashicorp/tap && brew install hashicorp/tap/terraform`
2. Make an SSH key: `ssh-keygen -t ed25519 -f ~/.ssh/lbstash_oci -C lbstash-oci`
3. Copy `terraform.tfvars.example` to `terraform.tfvars` and fill in the two OCIDs.
4. In the console, create the permissions from `policies.txt`.
5. In the console, create a private bucket `lbstash-tfstate` in the `LBStash` compartment with versioning on.

## Run

Easiest: **Actions > Terraform > Run workflow** on GitHub (plan, apply or destroy). Setup is in the main [README](../../README.md#deployment). Pull requests that change this folder get a plan automatically.

From your Mac:

```bash
cd infra/terraform
terraform init
terraform plan     # read what it will create
terraform apply
```

If apply says `Out of host capacity`, wait and apply again. Free ARM capacity comes and goes.

## Next

1. Point your domain's A record at the `public_ip` output (Cloudflare proxy on, SSL mode Full strict).
2. Log in with the `ssh_command` output. Only your key works.
3. Start the app: see [Deployment](../../README.md#deployment) in the main README.

## Change or remove

- Edit `terraform.tfvars` (for example `ssh_ingress_cidrs = ["your-ip/32"]`), then `terraform apply`. If you also apply from GitHub, keep `extra_ssh_public_keys` the same in both places, or the two runs will keep changing each other's result.
- Delete everything: `terraform destroy`.
