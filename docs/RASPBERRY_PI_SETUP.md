# Raspberry Pi setup

Target hardware: **Raspberry Pi 5, 8 or 16 GB**, running Raspberry Pi OS 64-bit
(Bookworm) or Ubuntu Server 24.04 LTS for arm64. This stack runs cleanly on
4 GB but 8+ GB is recommended because Docker image builds and Postgres like
breathing room.

## 1. OS prep

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git
```

## 2. Tailscale (optional, recommended)

So you can reach the Pi from anywhere:

```bash
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

The installer will print your Pi's Tailscale IP at the end.

## 3. Run the installer

From a clean shell:

```bash
curl -fsSL https://raw.githubusercontent.com/LSinstra/OdooPIAI/claude/odoo-ai-raspberry-pi-8I4Aa/install.sh \
  | sudo bash
```

You can preset variables before the pipe:

```bash
ODOOPIAI_BRANCH=main \
ODOOPIAI_DIR=/srv/odoopiai \
ODOOPIAI_USER=pi \
  curl -fsSL ... | sudo bash
```

## 4. What the installer leaves on disk

| Path                                                | Purpose                             |
| --------------------------------------------------- | ----------------------------------- |
| `/opt/odoopiai/`                                    | Git clone                           |
| `/opt/odoopiai/.env`                                | Secrets + config (chmod 600)        |
| `/etc/systemd/system/odoopiai.service`              | Keeps the stack up                  |
| `/etc/systemd/system/odoopiai-updater.service`      | One-shot pull+redeploy              |
| `/etc/systemd/system/odoopiai-updater.timer`        | Runs the updater every 30s          |
| `/usr/local/bin/odoopiai`                           | CLI helper                          |

## 5. Common tasks

```bash
odoopiai status          # service + container state
odoopiai logs            # tail api logs
odoopiai logs db         # tail postgres logs
odoopiai update          # pull + redeploy right now
odoopiai pause-updates   # stop the auto-update timer (debugging)
odoopiai resume-updates  # re-enable it
odoopiai shell           # bash inside the api container
odoopiai url             # print LAN + Tailscale URLs
```

## 6. Troubleshooting

**Docker install fails with 'curl: no certificate'**
Check system clock — `sudo timedatectl set-ntp true`.

**Containers keep OOMing**
You're probably on a 4 GB Pi. Either upgrade, or reduce Postgres's shared
buffers by dropping this into `docker-compose.override.yml`:

```yaml
services:
  db:
    command: postgres -c shared_buffers=128MB -c max_connections=20
```

**Auto-updates not firing**
```bash
sudo journalctl -u odoopiai-updater.service -n 50 --no-pager
sudo systemctl list-timers | grep odoopiai
```

If the Pi's working tree is dirty (someone edited files locally), the
updater skips that run — see the log line `working tree dirty, skipping`.
Either commit/stash locally on the Pi, or re-run `install.sh` to reset.

**I pushed, but the Pi didn't pick it up**
Make sure you pushed to the branch the `.env` is tracking:

```bash
grep UPDATE_BRANCH /opt/odoopiai/.env
```

Default is `claude/odoo-ai-raspberry-pi-8I4Aa`. Change it + `odoopiai restart`
to track a different branch.

## 7. Removing it

```bash
sudo odoopiai uninstall      # removes systemd units, keeps code + data
sudo rm -rf /opt/odoopiai    # if you want a full wipe
sudo docker volume rm odoopiai_db_data
```
