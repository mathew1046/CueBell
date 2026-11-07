#!/usr/bin/env bash
set -Eeuo pipefail
export PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
base=/home/ubuntu/cuebell-releases
repo=/home/ubuntu/queuesaathi
exec 8>"$base/watch.lock"
flock -n 8 || exit 0
git -C "$repo" fetch origin main
sha=$(git -C "$repo" rev-parse origin/main)
if [[ -f "$base/deployed-sha" ]] && [[ "$(< "$base/deployed-sha")" = "$sha" ]]; then exit 0; fi
if [[ -f "$base/failed-sha" ]] && [[ "$(< "$base/failed-sha")" = "$sha" ]]; then exit 0; fi
if /usr/local/libexec/cuebell-deploy "deploy $sha"; then
    rm -f "$base/failed-sha"
else
    printf '%s
' "$sha" > "$base/failed-sha"
    echo "Deployment failed for $sha. Existing service retained. Inspect journalctl -u cuebell-autodeploy." >&2
    exit 1
fi
