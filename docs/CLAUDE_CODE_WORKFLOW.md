# Iterating with Claude Code

This repo is designed for a tight loop:

```
Claude Code on laptop → git push → Pi pulls within 30s → live
```

## Typical session

```bash
# on your laptop
git clone git@github.com:lsinstra/odoopiai.git
cd odoopiai
git checkout claude/odoo-ai-raspberry-pi-8I4Aa
claude-code
```

Tell Claude what to change — prompts, a new feature, a styling fix — and let
it edit. When you're ready to see it on the Pi:

```bash
git add -A && git commit -m "…"
git push
```

Within ~30 seconds, the Pi's `odoopiai-updater.timer` fires, pulls, and
restarts the `api` container. Refresh your browser and you're on the new
version.

### See what the Pi is doing in real time

```bash
# from your laptop, over Tailscale:
ssh pi@<pi-tailscale-ip>
sudo journalctl -u odoopiai-updater.service -f
# and in another pane:
odoopiai logs
```

## Shortcut: force an immediate update

You can skip the 30 s wait and trigger the updater right now from the Pi:

```bash
odoopiai update
```

Or, from your laptop:

```bash
ssh pi@<pi> "sudo systemctl start odoopiai-updater.service"
```

## Fast vs slow rebuild

| Changed                                                  | Rebuild path                       | Typical time on Pi 5 |
| -------------------------------------------------------- | ---------------------------------- | -------------------- |
| `app/**/*.py`, `app/templates/**`, `app/static/**`       | container restart, no rebuild      | ~3–5 s               |
| `requirements.txt`, `Dockerfile`, `docker-compose.yml`   | full `docker compose build` + up   | ~1–3 min             |

The auto-updater chooses between the two automatically based on the files
changed in the pushed commit.

## When prompts are what you're iterating on

Prompts live in `app/services/prompts.py`. Change a prompt → commit → push →
Pi picks it up → try it in the browser. Because every Claude call keeps the
same system prompt on a stable cache breakpoint, the cache keeps hitting
between iterations as long as the system prompt text doesn't change. If you
edit a system prompt, expect the first call after deploy to miss cache and
be slightly slower.

## Pausing the updater for hand-debugging

If you want to `git pull` something experimental to the Pi without the timer
fighting you:

```bash
odoopiai pause-updates
# hack on the Pi...
odoopiai resume-updates
```

If you leave the tree dirty, the updater logs `working tree dirty, skipping`
every 30 s — it won't clobber your work.

## Branching strategy

- **Your iteration branch** (default: `claude/odoo-ai-raspberry-pi-8I4Aa`) —
  the Pi tracks this. Push freely.
- **`main`** — ship-ready. Merge when stable if you want a safer default.

To make the Pi track `main` instead:

```bash
# on the Pi
sudo -e /opt/odoopiai/.env    # change UPDATE_BRANCH=main
sudo systemctl restart odoopiai-updater.service
```

## Safety rails

The updater **refuses** to clobber a dirty working tree and **never**
force-pushes anything. The worst it can do if a bad commit lands is:

1. Run a broken build and fail-and-retry (old container stays up)
2. Deploy a broken app (old container stopped, new one crash-loops)

In case (2), roll back:

```bash
# on the Pi
cd /opt/odoopiai
git log --oneline -5
git reset --hard <previous-good-sha>
docker compose up -d --build
odoopiai pause-updates    # so the timer doesn't pull forward again
```

Then push the fix from your laptop and `odoopiai resume-updates`.
