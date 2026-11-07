#!/usr/bin/env bash
set -Eeuo pipefail
export PATH=/home/ubuntu/.local/bin:/usr/local/bin:/usr/bin:/bin
umask 077
command=${SSH_ORIGINAL_COMMAND:-${1:-}}
if [[ ! "$command" =~ ^deploy\ ([0-9a-f]{40})$ ]]; then
  echo 'Only deploy <40-character commit SHA> is allowed.' >&2; exit 2
fi
sha=${BASH_REMATCH[1]}
base=/home/ubuntu/cuebell-releases
repo=/home/ubuntu/queuesaathi
mkdir -p "$base"
exec 9>"$base/deploy.lock"
flock -w 600 9
git -C "$repo" fetch origin main
latest=$(git -C "$repo" rev-parse origin/main)
if [[ "$sha" != "$latest" ]]; then
  echo "Skipping superseded commit $sha; main is $latest"; exit 0
fi
release="$base/$sha"
if [[ -e "$release" ]]; then
  echo 'Release already exists; use workflow rerun after inspecting the server.' >&2; exit 1
fi
mkdir "$release"
git -C "$repo" archive "$sha" | tar -x -C "$release"
uv venv --python 3.12 "$release/backend/.venv"
uv pip install --python "$release/backend/.venv/bin/python" -r "$release/backend/requirements.lock"
uv pip install --python "$release/backend/.venv/bin/python" --no-deps -e "$release/backend"
(cd "$release/backend" && .venv/bin/pytest -q && .venv/bin/ruff check app tests && .venv/bin/ruff format --check app tests)
git -C "$repo" fetch origin main
if [[ "$sha" != "$(git -C "$repo" rev-parse origin/main)" ]]; then
  echo 'A newer commit arrived during validation; not promoting stale release.'; exit 0
fi
previous=$(readlink -f "$base/current")
ln -s "$release" "$base/next"
mv -Tf "$base/next" "$base/current"
healthy() {
  for attempt in {1..30}; do
    if curl -fsS --max-time 3 --resolve cuebell.mathewjoseph.xyz:443:13.206.26.235 https://cuebell.mathewjoseph.xyz/health | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="ok" and d["speech_configured"] and d["intent_configured"]' 2>/dev/null; then return 0; fi
    sleep 1
  done
  return 1
}
if sudo /usr/bin/systemctl restart queuesaathi && healthy; then
  printf '%s\n' "$sha" > "$base/deployed-sha"
  echo "Deployed $sha successfully: https://cuebell.mathewjoseph.xyz"
else
  echo 'Health failed; rolling back.' >&2
  ln -s "$previous" "$base/rollback"
  mv -Tf "$base/rollback" "$base/current"
  sudo /usr/bin/systemctl restart queuesaathi
  healthy || echo 'URGENT: rollback health failed' >&2
  exit 1
fi
