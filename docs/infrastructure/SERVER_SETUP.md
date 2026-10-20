# Server setup (Oracle Cloud + Terraform)

Builds the server with the **Terraform** workflow. Do this first. Then release the app: [RELEASE](../application/RELEASE.md).

You need: the Oracle setup from `infra/terraform/policies.txt`, `~/.oci/config` on your Mac, and the GitHub CLI (`gh auth status`).

## Steps

1. **Make a bucket** in the Oracle console (Storage > Buckets).
   Name `lbstash-tfstate`, compartment `LBStash`, private, versioning on. Terraform saves its state here.

2. **Add the secrets.** Make the deploy key and run **step A** in [SECRETS](../SECRETS.md). Do it before the first apply: adding the deploy key later may mean rebuilding the server.

3. **Build the server.** GitHub > Actions > **Terraform** > Run workflow > `apply`.
   Copy the `public_ip` from the run summary.

The server is an AMD VM, `VM.Standard.E5.Flex` with 1 OCPU (2 vCPU) and 4 GB RAM, Ubuntu 24.04, with a public IP. It is **paid**, but the 30-day Free Trial credit ($300) covers it (roughly $23 a month). Do not upgrade the Oracle account to Pay-As-You-Go while using it.

**Before day 30 of the trial**, move to a free server, or it stops: set `shape = "VM.Standard.A1.Flex"` (free up to 2 CPU and 12 GB) in `infra/terraform/variables.tf` and run the workflow. If Oracle answers "Out of host capacity", run it with **retry_minutes** set to `300`: it retries every minute until there is space. Back up the database first.

The free AMD micro (`VM.Standard.E2.1.Micro`) is far too small for this app (1 GB RAM, a fraction of a CPU).

## Later changes

Edit `infra/terraform` in a pull request (it shows the plan), merge, then run the workflow with `apply`.

To delete everything, run `destroy` and type `destroy` to confirm.

## Problems

| Problem | Fix |
|---|---|
| Fails at init | The `lbstash-tfstate` bucket is missing, or not in the `LBStash` compartment |
| "Out of host capacity" (ARM only) | Run with `retry_minutes` = `300`, or try again later |

Cost is about ₹0/month. Details of what gets built: [infra/terraform/README.md](../../infra/terraform/README.md).
