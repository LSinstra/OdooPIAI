#!/usr/bin/env bash
# =====================================================================
# Runs under systemd timer every 30s.
#   1. git fetch
#   2. If local branch is behind remote -> pull, rebuild, restart
#   3. Otherwise exit 0 (cheap — no build, no restart)
#
# Loud enough to follow via: journalctl -u odoopiai-updater.service -f
# =====================================================================
set -euo pipefail

INSTALL_DIR="${ODOOPIAI_DIR:-/opt/odoopiai}"
cd "$INSTALL_DIR"

BRANCH="$(grep -E '^UPDATE_BRANCH=' .env 2>/dev/null | cut -d= -f2 || echo main)"
[[ -z "$BRANCH" ]] && BRANCH="main"

log() { printf "[auto-update %s] %s\n" "$(date -Is)" "$*"; }

# Abort if repo is dirty — someone is hand-editing on the Pi.
if ! git diff --quiet || ! git diff --cached --quiet; then
  log "working tree dirty, skipping (run 'git stash' or commit locally)"
  exit 0
fi

git fetch --quiet origin "$BRANCH"
LOCAL="$(git rev-parse HEAD)"
REMOTE="$(git rev-parse "origin/$BRANCH")"

if [[ "$LOCAL" == "$REMOTE" ]]; then
  exit 0
fi

log "new commits on origin/$BRANCH: $LOCAL -> $REMOTE"
git checkout "$BRANCH"
git reset --hard "origin/$BRANCH"

# Only rebuild if image-relevant files changed — keeps hot reloads snappy.
CHANGED="$(git diff --name-only "$LOCAL" "$REMOTE" || true)"
if echo "$CHANGED" | grep -Eq '^(Dockerfile|requirements\.txt|docker-compose\.yml|scripts/entrypoint\.sh)$'; then
  log "image files changed — rebuilding"
  docker compose build
  docker compose up -d
else
  # App-only change. The app/ dir is bind-mounted, but uvicorn runs without
  # --reload, so we MUST restart the api container to pick up new routes.
  # `up -d` is a no-op when the service config hasn't changed — use restart.
  log "app code changed — restarting api container (no rebuild)"
  docker compose restart api
fi

log "update complete"
