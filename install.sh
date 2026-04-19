#!/usr/bin/env bash
# =====================================================================
# OdooPIAI — Raspberry Pi installer / runner
#
# What this does, one-shot:
#   1. Installs Docker + Compose plugin (if missing)
#   2. Clones the repo to /opt/odoopiai (or pulls if already there)
#   3. Generates .env with strong random secrets, prompts for API keys
#   4. Builds and starts the stack via `docker compose`
#   5. Registers two systemd units:
#        - odoopiai.service          keeps the stack up on boot
#        - odoopiai-updater.service  + .timer  polls git + redeploys
#   6. Installs the `odoopiai` CLI helper to /usr/local/bin
#
# Run on a fresh Pi (arm64, Raspberry Pi OS or Ubuntu):
#   curl -fsSL https://raw.githubusercontent.com/LSinstra/OdooPIAI/<branch>/install.sh | sudo bash
# or, after cloning manually:
#   sudo bash install.sh
# =====================================================================
set -euo pipefail

REPO_URL_DEFAULT="https://github.com/lsinstra/odoopiai.git"
INSTALL_DIR="${ODOOPIAI_DIR:-/opt/odoopiai}"
BRANCH_DEFAULT="${ODOOPIAI_BRANCH:-claude/odoo-ai-raspberry-pi-8I4Aa}"
SERVICE_USER="${ODOOPIAI_USER:-$SUDO_USER}"
[[ -z "${SERVICE_USER:-}" || "$SERVICE_USER" == "root" ]] && SERVICE_USER="$(logname 2>/dev/null || echo pi)"

log()  { printf "\033[1;36m[odoopiai]\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33m[odoopiai]\033[0m %s\n" "$*" >&2; }
die()  { printf "\033[1;31m[odoopiai]\033[0m %s\n" "$*" >&2; exit 1; }

[[ "$EUID" -eq 0 ]] || die "Run as root (sudo bash install.sh)"

# ---- 1. Docker ------------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
  log "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
  usermod -aG docker "$SERVICE_USER" || true
else
  log "Docker already installed: $(docker --version)"
fi

if ! docker compose version >/dev/null 2>&1; then
  log "Installing docker compose plugin..."
  apt-get update
  apt-get install -y docker-compose-plugin
fi

# ---- 2. Clone / update repo ----------------------------------------
if [[ ! -d "$INSTALL_DIR/.git" ]]; then
  REPO_URL="${ODOOPIAI_REPO:-$REPO_URL_DEFAULT}"
  BRANCH="${ODOOPIAI_BRANCH:-$BRANCH_DEFAULT}"
  log "Cloning $REPO_URL (branch $BRANCH) to $INSTALL_DIR"
  git clone --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR"
else
  log "Repo present at $INSTALL_DIR, fetching latest..."
  git -C "$INSTALL_DIR" fetch --all --prune
  git -C "$INSTALL_DIR" checkout "${ODOOPIAI_BRANCH:-$BRANCH_DEFAULT}"
  git -C "$INSTALL_DIR" pull --ff-only
fi
chown -R "$SERVICE_USER":"$SERVICE_USER" "$INSTALL_DIR"

# ---- 3. .env generation --------------------------------------------
ENV_FILE="$INSTALL_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  log "Creating $ENV_FILE"
  cp "$INSTALL_DIR/.env.example" "$ENV_FILE"

  APP_SECRET_KEY="$(docker run --rm python:3.12-slim python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())' 2>/dev/null || python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
  JWT_SECRET="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  PG_PASS="$(python3 -c 'import secrets; print(secrets.token_urlsafe(24))')"

  sed -i "s|^APP_SECRET_KEY=.*|APP_SECRET_KEY=$APP_SECRET_KEY|" "$ENV_FILE"
  sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$JWT_SECRET|" "$ENV_FILE"
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PG_PASS|" "$ENV_FILE"

  if [[ -t 0 ]]; then
    read -rp "Anthropic API key (sk-ant-...): " ANTH_KEY
    if [[ -n "${ANTH_KEY:-}" ]]; then
      sed -i "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$ANTH_KEY|" "$ENV_FILE"
    fi
  else
    warn "Non-interactive — edit $ENV_FILE to set ANTHROPIC_API_KEY before first use."
  fi
  chown "$SERVICE_USER":"$SERVICE_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
else
  log ".env already present — preserving."
fi

# ---- 4. Build + start ----------------------------------------------
log "Building containers (first time can be ~5 min on Pi 5)..."
( cd "$INSTALL_DIR" && docker compose build )

log "Starting stack..."
( cd "$INSTALL_DIR" && docker compose up -d )

# ---- 5. systemd units ----------------------------------------------
log "Registering systemd units..."
install -m 0644 "$INSTALL_DIR/systemd/odoopiai.service" /etc/systemd/system/odoopiai.service
install -m 0644 "$INSTALL_DIR/systemd/odoopiai-updater.service" /etc/systemd/system/odoopiai-updater.service
install -m 0644 "$INSTALL_DIR/systemd/odoopiai-updater.timer" /etc/systemd/system/odoopiai-updater.timer

# Patch paths/user into the units.
sed -i "s|@INSTALL_DIR@|$INSTALL_DIR|g" /etc/systemd/system/odoopiai*.service
sed -i "s|@SERVICE_USER@|$SERVICE_USER|g" /etc/systemd/system/odoopiai*.service

systemctl daemon-reload
systemctl enable --now odoopiai.service
systemctl enable --now odoopiai-updater.timer

# ---- 6. CLI helper -------------------------------------------------
install -m 0755 "$INSTALL_DIR/scripts/odoopiai" /usr/local/bin/odoopiai
log "Installed 'odoopiai' CLI helper (try: odoopiai status)"

# ---- 7. Summary ----------------------------------------------------
TS_IP="$(tailscale ip -4 2>/dev/null | head -n1 || true)"
LAN_IP="$(hostname -I | awk '{print $1}')"
PORT="$(grep -E '^APP_PORT=' "$ENV_FILE" | cut -d= -f2 || echo 8080)"

echo
log "================================================="
log " OdooPIAI is up."
log "-------------------------------------------------"
log " LAN         : http://${LAN_IP}:${PORT}"
[[ -n "$TS_IP" ]] && log " Tailscale   : http://${TS_IP}:${PORT}"
[[ -z "$TS_IP" ]] && warn " Tailscale   : not detected. Install with:  curl -fsSL https://tailscale.com/install.sh | sh  && sudo tailscale up"
log " Logs        : odoopiai logs"
log " Auto-update : polls git branch every ${UPDATE_INTERVAL_SECONDS:-30}s"
log " Config      : $ENV_FILE"
log "================================================="
