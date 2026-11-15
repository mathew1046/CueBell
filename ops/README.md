# Deployment operations

`ops/` keeps deployment reference scripts and service templates in version control. The app itself does not import this directory.

## What runs in production

The current server installs reviewed deployment entrypoints separately:

- `/usr/local/libexec/cuebell-watch`: polls `origin/main` and skips deployed or previously failed commits.
- `/usr/local/libexec/cuebell-deploy`: builds a release, runs checks, promotes it and rolls back on failed readiness.
- `cuebell-autodeploy.timer`: starts the watcher roughly every minute after its previous check finishes.
- `queuesaathi.service`: runs the FastAPI relay. This is a retained service name, not a second product.
- `cuebell-web.service`: serves the production web export.

**The checked-in `deploy-backend.sh` and `watch-backend.sh` are earlier backend-only reference versions.** The installed entrypoints have since been extended for frontend tests/builds and restarting both services. Copying these older scripts over the installed files would lose that support. Changes to this folder do not automatically replace trusted entrypoints.

## Release flow

1. Fetch the latest `main` commit and serialize deployments.
2. Archive that exact SHA under `/home/ubuntu/cuebell-releases/<SHA>`.
3. Install locked Python and Node dependencies. Run backend tests/lint/formatting, frontend unit tests/types/lint, and build the web export with its public API origin.
4. Confirm the commit is still current `main`, then atomically switch the `current` symlink.
5. Restart both services and verify public backend health and frontend readiness. On readiness failure, restore the previous release.

Releases retain separate Python environments and frontend builds. Backend credentials stay in the protected environment file outside the archives. Restarting the relay clears in-memory sessions. Automatic rollback does not reverse database migrations; the current relay has no database.

GitHub CI runs independently. The server deployment gate does not run the entire browser/audio suite; see [verification](../docs/VERIFICATION.md) for the distinction.

## Inspect or pause

```sh
systemctl status queuesaathi cuebell-web cuebell-autodeploy.timer
journalctl -u cuebell-autodeploy.service -n 80 --no-pager
readlink -f /home/ubuntu/cuebell-releases/current
cat /home/ubuntu/cuebell-releases/deployed-sha
curl --fail https://cuebell.mathewjoseph.xyz/health
curl --fail --output /dev/null https://cuebell.mathewjoseph.xyz/

# Pause only CueBell automatic deployment.
sudo systemctl stop cuebell-autodeploy.timer
# Resume it.
sudo systemctl start cuebell-autodeploy.timer
```

A failed SHA is not retried every minute. Inspect the failure before retrying or deleting an inactive failed release. Keep the current and previous known-good releases for rollback and monitor disk usage.

## Hosting boundaries

The reverse proxy serves both layers on one origin. Route `/v1/` and `/health` to the loopback relay before the frontend catch-all, preserve WebSocket upgrades and set the forwarded HTTPS scheme. Keep provider secrets server-side and use an exact browser origin allowlist.

Public demo admission can spend paid provider quota. Rate limits are not production identity; add suitable access controls and provider budgets before wider use. See [backend setup](../backend/README.md), [web setup](../docs/WEB.md) and [security](../SECURITY.md).
