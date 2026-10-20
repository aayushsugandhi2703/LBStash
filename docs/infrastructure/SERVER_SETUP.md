# Server setup (Oracle Cloud + Terraform)

Builds the server with the **Terraform** workflow. Do this first. Then release the app: [RELEASE](../application/RELEASE.md).

You need: the Oracle setup from `infra/terraform/policies.txt`, `~/.oci/config` on your Mac, and the GitHub CLI (`gh auth status`).

## Steps

1. **Make a bucket** in the Oracle console (Storage > Buckets).
   Name `lbstash-tfstate`, compartment `LBStash`, private, versioning on. Terraform saves its state here.

2. **Add the secrets.** Make the deploy key and run **step A** in [SECRETS](SECRETS.md). Do it before the first apply: adding the deploy key later may mean rebuilding the server.

3. **Build the server.** GitHub > Actions > **Terraform** > Run workflow > `apply`.
   Copy the `public_ip` from the run summary.

"Out of host capacity" means Oracle has no free ARM space right now. It is common and usually clears within hours. Run the workflow with **retry_minutes** set to `300`: it tries again every minute until the VM is created (it stops after 5 hours; run it again if it gives up). The network and firewall are already built, so only the VM is retried.

The VM is small on purpose (1 CPU, 6 GB, set by `ocpus` and `memory_gb` in `infra/terraform/variables.tf`) because small requests find free space more easily, and the app needs only about 3 GB. If you want the full free size, set them to `2` and `12` and run `apply`.

## Later changes

Edit `infra/terraform` in a pull request (it shows the plan), merge, then run the workflow with `apply`.

To delete everything, run `destroy` and type `destroy` to confirm.

## Problems

| Problem | Fix |
|---|---|
| Fails at init | The `lbstash-tfstate` bucket is missing, or not in the `LBStash` compartment |
| "Out of host capacity" | Run with `retry_minutes` = `300`, or try again later |

Cost is about ₹0/month. Details of what gets built: [infra/terraform/README.md](../../infra/terraform/README.md).
