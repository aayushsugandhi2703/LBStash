# GitHub secrets and variables

Everything GitHub needs, in one place. Add them here, nowhere else.

Where: GitHub > Settings > Secrets and variables > Actions. Or use the commands below (needs the GitHub CLI, `gh auth status`).

## What to add

| Name | Type | Used by | Value |
|---|---|---|---|
| `OCI_TENANCY_OCID` | secret | Terraform | `tenancy=` in `~/.oci/config` |
| `OCI_USER_OCID` | secret | Terraform | `user=` in `~/.oci/config` |
| `OCI_FINGERPRINT` | secret | Terraform | `fingerprint=` in `~/.oci/config` |
| `OCI_COMPARTMENT_OCID` | secret | Terraform | `compartment_ocid` in `infra/terraform/terraform.tfvars` |
| `OCI_PRIVATE_KEY` | secret | Terraform | file `~/.oci/tf_key.pem` |
| `SSH_PUBLIC_KEY` | secret | Terraform | file `~/.ssh/lbstash_oci.pub` |
| `DEPLOY_SSH_PUBLIC_KEY` | secret | Terraform | file `~/.ssh/lbstash_deploy.pub` |
| `DOCKERHUB_TOKEN` | secret | Release | Docker Hub access token (below) |
| `VM_SSH_PRIVATE_KEY` | secret | Release | file `~/.ssh/lbstash_deploy` |
| `VM_HOST` | secret | Release | `public_ip` from the Terraform run |
| `LETSENCRYPT_EMAIL` | variable | Release | your email (empty if you use the Cloudflare Tunnel) |

10 secrets and 1 variable. `GITHUB_TOKEN` is automatic.

Only real credentials and private IDs are here. Your email stays a variable because the repo is public.

## Kept in files instead (not secret)

| Value | Where | Why it is safe |
|---|---|---|
| Domain `lbstash.site` | `DOMAIN` in `.env.example` | It is public anyway. Deploy and the status badge read it from here |
| Docker Hub username `aayush2703` | `HUB_USER` and `REGISTRY` in `.github/workflows/release.yml` | Public on Docker Hub |
| VM type (free AMD micro) | `shape` in `infra/terraform/variables.tf` | A setting |

To change any of these, edit the file and push.

## Make these first

1. **Deploy key** (only GitHub uses it):
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/lbstash_deploy -C lbstash-deploy
   ```
   Make it before the first Terraform apply. Adding it later may mean rebuilding the server. If you also run Terraform on your Mac, put its public key in `infra/terraform/terraform.tfvars` as `extra_ssh_public_keys` (see `terraform.tfvars.example`), so both give the same result.

2. **Docker Hub token:** hub.docker.com > Account settings > Personal access tokens > New, with **Read, Write, Delete**. Copy it.

## Add them

Run in the repo folder.

**Step A: before Terraform** (everything except `VM_HOST`):

```bash
cfg=~/.oci/config
gh secret set OCI_TENANCY_OCID --body "$(awk -F= '/^tenancy=/{print $2}' $cfg)"
gh secret set OCI_USER_OCID --body "$(awk -F= '/^user=/{print $2}' $cfg)"
gh secret set OCI_FINGERPRINT --body "$(awk -F= '/^fingerprint=/{print $2}' $cfg)"
gh secret set OCI_COMPARTMENT_OCID --body "$(awk -F'"' '/^compartment_ocid/{print $2}' infra/terraform/terraform.tfvars)"
gh secret set OCI_PRIVATE_KEY < ~/.oci/tf_key.pem
gh secret set SSH_PUBLIC_KEY < ~/.ssh/lbstash_oci.pub
gh secret set DEPLOY_SSH_PUBLIC_KEY < ~/.ssh/lbstash_deploy.pub
gh secret set VM_SSH_PRIVATE_KEY < ~/.ssh/lbstash_deploy
gh secret set DOCKERHUB_TOKEN        # paste the token when asked
gh variable set LETSENCRYPT_EMAIL --body "<your email>"
```

**Step B: after Terraform** (the server's IP is known only then):

```bash
gh secret set VM_HOST --body "<public_ip from the Terraform run summary>"
```

## Check

```bash
gh secret list     # 10 after step B
gh variable list   # LETSENCRYPT_EMAIL
```

## Order of everything

1. Make the two things above. Run step A.
2. Create the `lbstash-tfstate` bucket and run the Terraform workflow: [SERVER_SETUP](SERVER_SETUP.md).
3. Run step B. Then release the app: [RELEASE](../application/RELEASE.md).
