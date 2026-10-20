# GitHub secrets and variables

Every secret and variable the workflows need, in one place. Add them here, nowhere else.

Where: GitHub > Settings > Secrets and variables > Actions. Or use the commands below (needs the GitHub CLI, `gh auth status`).

## Everything you need to add

| Name | Type | Used by | Value |
|---|---|---|---|
| `OCI_TENANCY_OCID` | secret | Terraform | `tenancy=` in `~/.oci/config` |
| `OCI_USER_OCID` | secret | Terraform | `user=` in `~/.oci/config` |
| `OCI_FINGERPRINT` | secret | Terraform | `fingerprint=` in `~/.oci/config` |
| `OCI_COMPARTMENT_OCID` | secret | Terraform | `compartment_ocid` in `infra/terraform/terraform.tfvars` |
| `OCI_PRIVATE_KEY` | secret | Terraform | file `~/.oci/tf_key.pem` |
| `SSH_PUBLIC_KEY` | secret | Terraform | file `~/.ssh/lbstash_oci.pub` |
| `DEPLOY_SSH_PUBLIC_KEY` | secret | Terraform | file `~/.ssh/lbstash_deploy.pub` |
| `DOCKERHUB_USERNAME` | secret | Release | your Docker Hub username |
| `DOCKERHUB_TOKEN` | secret | Release | Docker Hub access token (below) |
| `VM_HOST` | secret | Release | `public_ip` from the Terraform run |
| `VM_SSH_PRIVATE_KEY` | secret | Release | file `~/.ssh/lbstash_deploy` |
| `DOMAIN` | variable | Release, Status | `lbstash.site` |
| `LETSENCRYPT_EMAIL` | variable | Release | your email (empty if you use the Cloudflare Tunnel) |

12 secrets and 2 variables. `GITHUB_TOKEN` is automatic.

## Make these first

1. **Deploy key** (only GitHub uses it):
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/lbstash_deploy -C lbstash-deploy
   ```
   Make it before the first Terraform apply. Adding it later may mean rebuilding the server.

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
gh secret set DOCKERHUB_USERNAME --body "<your Docker Hub username>"
gh secret set DOCKERHUB_TOKEN --body "<the token>"
gh variable set DOMAIN --body "lbstash.site"
gh variable set LETSENCRYPT_EMAIL --body "<your email>"
```

**Step B: after Terraform** (the server's IP is known only then):

```bash
gh secret set VM_HOST --body "<public_ip from the Terraform run summary>"
```

## Check

```bash
gh secret list     # should show 12 after step B
gh variable list   # should show DOMAIN and LETSENCRYPT_EMAIL
```

## Order of everything

1. Make the two things above. Run step A.
2. Create the `lbstash-tfstate` bucket and run the Terraform workflow: [SERVER_SETUP](infrastructure/SERVER_SETUP.md).
3. Run step B. Then release the app: [RELEASE](application/RELEASE.md).

Keep your email out of files. The repo is public.
