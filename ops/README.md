# Backend continuous deployment

Every new commit pushed to `main` is detected by the server's `cuebell-autodeploy.timer` (60 seconds after the previous check completes). Existing GitHub `Checks` runs separately. Deployment validation runs on the server and does not depend on GitHub Actions availability. PR branches do not deploy.

GitHub authentication currently lacks `workflow` scope, so no GitHub deployment workflow or deployment SSH secret is used. The server uses its existing authenticated Git access. Only trusted main-branch code should be merged: backend tests and package installation execute on this host.

## Deployment flow

1. Fetch current `origin/main`, serialize deployments using flock, and skip already deployed/previously failed commits.
2. Archive the exact main commit to `/home/ubuntu/cuebell-releases/<SHA>` and install locked dependencies into a dedicated virtual environment.
3. Run pytest, Ruff lint and Ruff formatting checks. If any fail, retain the running release.
4. Check that the commit is still current main, atomically switch `current`, and restart `queuesaathi.service`.
5. Verify HTTPS health, including provider-configuration flags. If startup or readiness fails, switch back to the previous release and restart it. Superseded commits are skipped rather than deployed out of order.

API keys stay in `/home/ubuntu/queuesaathi/backend/.env` (mode 600), outside release archives and Git. The systemd EnvironmentFile uses that original path. The override in `/etc/systemd/system/queuesaathi.service.d/release.conf` launches `current/backend/.venv/bin/uvicorn` with working directory `current/backend`. In-flight sessions reset on restart.

Installed entrypoints `/usr/local/libexec/cuebell-watch` and `/usr/local/libexec/cuebell-deploy` are root-owned reviewed copies of these scripts. Updating scripts in Git does not automatically replace the trusted entrypoints.

## Operations

- Health: https://cuebell.mathewjoseph.xyz/health
- Deployment logs: `journalctl -u cuebell-autodeploy.service`
- Timer: `systemctl status cuebell-autodeploy.timer`
- Running service: `systemctl status queuesaathi`
- Deployed SHA: `/home/ubuntu/cuebell-releases/deployed-sha`
- Stop auto-deployment: `sudo systemctl disable --now cuebell-autodeploy.timer`
- A failed commit is not retried every minute. Push a fix. To retry the same SHA, inspect the failure first, remove only its inactive release directory and `failed-sha`, then start the oneshot service.
- Manual rollback: atomically point `current` at a validated previous release, restart the backend, and verify HTTPS. Pause the timer before a manual rollback to avoid redeployment of main.

Old releases are retained for rollback. Monitor disk space and remove unused releases, never `current` or the previous known-good release. Automatic rollback does not reverse database migrations. Sessions currently live in memory.
