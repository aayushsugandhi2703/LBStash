# Server setup (Oracle Cloud + Terraform)

Builds the server with the **Terraform** workflow. Do this first. Then release the app: [RELEASE](../application/RELEASE.md).

You need: the Oracle setup from `infra/terraform/policies.txt`, `~/.oci/config` on your Mac, and the GitHub CLI (`gh auth status`).

## Steps

1. **Make a bucket** in the Oracle console (Storage > Buckets).
   Name `lbstash-tfstate`, compartment `LBStash`, private, versioning on. Terraform saves its state here.

2. **Add the secrets.** Make the deploy key and run **step A** in [SECRETS](SECRETS.md). Do it before the first apply: adding the deploy key later may mean rebuilding the server.

3. **Build the server.** GitHub > Actions > **Terraform** > Run workflow > `apply`.
   Copy the `public_ip` from the run summary.

The server is Oracle's free AMD micro VM (`VM.Standard.E2.1.Micro`): Ubuntu 24.04, 1 GB RAM plus 4 GB of swap, and a public IP. It is almost always available.

It is small for this app (about 3 GB wanted), so it runs slowly and starts slowly. For more room, use the free ARM VM instead: set `shape = "VM.Standard.A1.Flex"` in `infra/terraform/variables.tf`. If Oracle answers "Out of host capacity", run the workflow with **retry_minutes** set to `300`: it retries every minute until there is space.

## Later changes

Edit `infra/terraform` in a pull request (it shows the plan), merge, then run the workflow with `apply`.

To delete everything, run `destroy` and type `destroy` to confirm.

## Problems

| Problem | Fix |
|---|---|
| Fails at init | The `lbstash-tfstate` bucket is missing, or not in the `LBStash` compartment |
| "Out of host capacity" (ARM only) | Run with `retry_minutes` = `300`, or use the micro |

Cost is about ₹0/month. Details of what gets built: [infra/terraform/README.md](../../infra/terraform/README.md).
