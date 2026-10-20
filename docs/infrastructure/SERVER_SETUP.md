# Server setup (Oracle Cloud + Terraform)

Builds the server with the **Terraform** workflow. Do this first. Then release the app: [RELEASE](../application/RELEASE.md).

You need: the Oracle setup from `infra/terraform/policies.txt`, `~/.oci/config` on your Mac, and the GitHub CLI (`gh auth status`).

## Steps

1. **Make a bucket** in the Oracle console (Storage > Buckets).
   Name `lbstash-tfstate`, compartment `LBStash`, private, versioning on. Terraform saves its state here.

2. **Make a deploy key** (only GitHub uses it):
   ```bash
   ssh-keygen -t ed25519 -N "" -f ~/.ssh/lbstash_deploy -C lbstash-deploy
   ```
   Make it before the first apply. Adding it later may mean rebuilding the server.

3. **Add the secrets** (run in the repo folder):
   ```bash
   cfg=~/.oci/config
   gh secret set OCI_TENANCY_OCID --body "$(awk -F= '/^tenancy=/{print $2}' $cfg)"
   gh secret set OCI_USER_OCID --body "$(awk -F= '/^user=/{print $2}' $cfg)"
   gh secret set OCI_FINGERPRINT --body "$(awk -F= '/^fingerprint=/{print $2}' $cfg)"
   gh secret set OCI_COMPARTMENT_OCID --body "$(awk -F'"' '/^compartment_ocid/{print $2}' infra/terraform/terraform.tfvars)"
   gh secret set OCI_PRIVATE_KEY < ~/.oci/tf_key.pem
   gh secret set SSH_PUBLIC_KEY < ~/.ssh/lbstash_oci.pub
   gh secret set DEPLOY_SSH_PUBLIC_KEY < ~/.ssh/lbstash_deploy.pub
   ```

4. **Build the server.** GitHub > Actions > **Terraform** > Run workflow > `apply`.
   Copy the `public_ip` from the run summary.

"Out of host capacity" means Oracle has no free ARM space right now. Wait and run it again.

## Later changes

Edit `infra/terraform` in a pull request (it shows the plan), merge, then run the workflow with `apply`.

To delete everything, run `destroy` and type `destroy` to confirm.

## Secrets

GitHub > Settings > Secrets and variables > Actions.

| Name | Value |
|---|---|
| `OCI_TENANCY_OCID` | `tenancy=` in `~/.oci/config` |
| `OCI_USER_OCID` | `user=` in `~/.oci/config` |
| `OCI_FINGERPRINT` | `fingerprint=` in `~/.oci/config` |
| `OCI_COMPARTMENT_OCID` | Console > Compartments > LBStash |
| `OCI_PRIVATE_KEY` | file `~/.oci/tf_key.pem` |
| `SSH_PUBLIC_KEY` | file `~/.ssh/lbstash_oci.pub` |
| `DEPLOY_SSH_PUBLIC_KEY` | file `~/.ssh/lbstash_deploy.pub` |

## Problems

| Problem | Fix |
|---|---|
| Fails at init | The `lbstash-tfstate` bucket is missing, or not in the `LBStash` compartment |
| "Out of host capacity" | Wait, run again |

Cost is about ₹0/month. Details of what gets built: [infra/terraform/README.md](../../infra/terraform/README.md).
