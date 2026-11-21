#!/usr/bin/env bash
# Build and run a revision of phi on heavypad. Run it there, from this checkout:
#   deploy/heavypad/deploy.sh [git-ref]     (default: origin/main)
# The previous image stays tagged phi:previous; if the new one is not healthy
# within two minutes the script puts it back and exits non-zero.
set -euo pipefail

cd "$(dirname "$0")/../.."
export DOCKER_HOST=unix:///var/run/docker.sock
ref=${1:-origin/main}
health=http://127.0.0.1:8801/health

git fetch --quiet origin
git checkout --quiet --detach "$ref"
rev=$(git rev-parse --short HEAD)

docker build --quiet -t "phi:$rev" .
if docker image inspect phi:current >/dev/null 2>&1; then
  docker tag phi:current phi:previous
fi
docker tag "phi:$rev" phi:current

install -m 0644 deploy/heavypad/phi.service "$HOME/.config/systemd/user/phi.service"
systemctl --user daemon-reload
systemctl --user enable --quiet phi.service
systemctl --user restart phi.service

healthy() {
  for _ in $(seq 1 24); do
    sleep 5
    status=$(curl -fsS -m 5 "$health" | python3 -c 'import json,sys; print(json.load(sys.stdin)["status"])' 2>/dev/null || true)
    [ "$status" = healthy ] || [ "$status" = degraded ] && return 0
  done
  return 1
}

if healthy; then
  echo "phi $rev is $status"
  exit 0
fi

echo "phi $rev did not become healthy; restoring the previous image" >&2
if docker image inspect phi:previous >/dev/null 2>&1; then
  docker tag phi:previous phi:current
  systemctl --user restart phi.service
fi
exit 1
