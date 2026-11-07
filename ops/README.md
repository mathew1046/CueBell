# Backend continuous deployment

Every push to `main` runs `.github/workflows/deploy-backend.yml`. It installs locked Python dependencies, runs backend tests, lint and formatting, then invokes a restricted SSH deployment command. Pull requests cannot deploy.

GitHub secrets `CUEBELL_DEPLOY_KEY` and `CUEBELL_KNOWN_HOSTS` contain a deployment-only SSH key and the pinned server host key. API keys remain only in `/home/ubuntu/queuesaathi/backend/.env` (mode 600). Never commit that file.

The server's authorized key uses `restrict,command="/usr/local/libexec/cuebell-deploy"`. It accepts only `deploy <40-character SHA>`, validates the SHA against current `origin/main`, and serializes deployments with flock. The installed script is a root-owned copy of `ops/deploy-backend.sh`; changing the repository script does not silently change the trusted entrypoint.

Releases live in `/home/ubuntu/cuebell-releases/<SHA>`, with separate virtual environments. Tests run again on the server before an atomic `current` symlink switch. A systemd override points `queuesaathi.service` at `current/backend`, while its EnvironmentFile remains outside releases. Failed startup/HTTPS readiness checks switch back to the previous release and fail the workflow. In-flight sessions reset when the service restarts. Superseded commits are skipped rather than deployed out of order.

Health: https://cuebell.mathewjoseph.xyz/health

Inspect: `systemctl status queuesaathi`, `journalctl -u queuesaathi`, and `/home/ubuntu/cuebell-releases/deployed-sha`.

Manual rollback: change `current` atomically to a previously validated release, restart `queuesaathi`, and verify HTTPS health. Automatic rollback does not reverse database migrations. This backend currently holds sessions in memory.

Old release directories are retained for rollback. Monitor disk space and remove unused releases, never `current` or the previous known-good release. To update the trusted entrypoint, review it then install using `sudo install -m 755 ops/deploy-backend.sh /usr/local/libexec/cuebell-deploy`.
