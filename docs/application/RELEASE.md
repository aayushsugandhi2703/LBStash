# Release and deploy (the app)

The **Release** workflow builds the images, stores them on Docker Hub, and updates the server. The server must exist first: [SERVER_SETUP](../infrastructure/SERVER_SETUP.md).

```
Release workflow --> builds images (amd64 + arm64) --> Docker Hub --> server pulls :latest and restarts
```

## First time

1. **Make a Docker Hub token.** hub.docker.com > Account settings > Personal access tokens > New, with **Read, Write, Delete**. Copy it.

2. **Add the secrets and variables:**
   ```bash
   gh secret set DOCKERHUB_USERNAME --body "<your Docker Hub username>"
   gh secret set DOCKERHUB_TOKEN --body "<the token>"
   gh secret set VM_HOST --body "<public_ip>"
   gh secret set VM_SSH_PRIVATE_KEY < ~/.ssh/lbstash_deploy
   gh variable set DOMAIN --body "lbstash.site"
   gh variable set LETSENCRYPT_EMAIL --body "<your email>"
   ```

3. **Set up Cloudflare.**
   DNS: add an `A` record, name `@`, value the `public_ip`, proxy on.
   SSL/TLS: set the mode to **Full (strict)**.

4. **First release.** Actions > **Release** > Run workflow > version `0.1.0`.
   It builds the images (about 15 minutes), creates the server's `.env`, starts the app, and gets the https certificate.

5. **Back up `FIELD_KEY`.** Without it, encrypted data cannot be read.
   ```bash
   ssh -i ~/.ssh/lbstash_deploy ubuntu@<public_ip> grep FIELD_KEY lbstash/.env
   ```

6. **Open https://lbstash.site**, create your account and follow the in-app Setup guide for Telegram.

## Next releases

1. Merge your pull request into `main`.
2. Actions > **Release** > Run workflow > the next version.

Release pushes `lbstash-<name>:<version>` and `:latest` for all 10 images to Docker Hub, deploys (the server pulls the new `:latest`), deletes older version tags, bumps the version, updates [CHANGELOG](CHANGELOG.md) and tags `vX.Y.Z`. Nothing deploys until you run it. Run it from `main`. Each version works once. To skip the deploy, untick **deploy**.

Versions are `x.y.z`: x = major change or new feature, y = UI change or fix, z = bug fix.

Images are created as **public** repos on the first push (the free plan allows unlimited public repos). They hold no secrets, so the server pulls them without logging in.

To roll back, set `IMAGE_TAG=<old version>` in the server's `.env` and run `docker compose up -d`. Only the latest version's tags are kept, so roll back to the most recent one.

The **Update status badge** workflow checks the site every 15 minutes for the README badge. It starts once `DOMAIN` is set.

## Secrets and variables

GitHub > Settings > Secrets and variables > Actions.

| Name | Type | Value |
|---|---|---|
| `DOCKERHUB_USERNAME` | secret | your Docker Hub username |
| `DOCKERHUB_TOKEN` | secret | the access token from step 1 |
| `VM_HOST` | secret | `public_ip` from the Terraform run |
| `VM_SSH_PRIVATE_KEY` | secret | file `~/.ssh/lbstash_deploy` |
| `DOMAIN` | variable | `lbstash.site` |
| `LETSENCRYPT_EMAIL` | variable | your email (empty if you use the Cloudflare Tunnel) |

Keep your email out of files. The repo is public.

## Problems

| Problem | Fix |
|---|---|
| Version exists | Use the next version |
| Run from main | Merge the pull request first |
| Docker login fails | Check `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (needs Read, Write, Delete) |
| Deploy cannot connect | Check `VM_HOST` and `VM_SSH_PRIVATE_KEY`. The deploy key must be in place at the first apply |
| Too many redirects | Cloudflare SSL/TLS must be **Full (strict)** |
| https error | DNS must point at the IP. The certificate retries every 30 minutes |
| Last step cannot push | `main` is protected: let the GitHub Actions bot push |

Look inside the server:
```bash
ssh -i ~/.ssh/lbstash_deploy ubuntu@<public_ip>
cd lbstash && docker compose ps
```

Backups are not automatic yet.
