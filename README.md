# OdooPIAI

Claude-powered Odoo 17 project-management copilot, purpose-built to run on a
**Raspberry Pi 5** and auto-redeploy itself whenever you push new code.

- **Plan with AI** — brief → stages + tasks + estimates → one-click apply to Odoo
- **Task breakdown** — parent task → 3–8 subtasks, wired via `parent_id`
- **Ask AI (streaming)** — grounded chat against the project's live state; optional post to chatter
- **Daily standup digest** — cron job posts a standup brief to each project's chatter
- **Risk scan** — every few hours, flags overdue / overloaded / stale tasks as local insights
- **Stakeholder update drafter** — exec / customer / internal tone presets

## Stack (chosen to be Pi-friendly + iteration-friendly)

- **FastAPI + Jinja2 + HTMX + Alpine.js + Tailwind (CDN)** — no Node build step, seconds-fast iteration
- **Postgres 16** in a sidecar container
- **APScheduler** in-process for the cron jobs
- **Anthropic SDK** — Opus 4.7 for reasoning, Haiku 4.5 for cheap digests
- **systemd** units keep it up on boot and auto-pull new commits from your branch

## Quick start on a Raspberry Pi 5

```bash
# On the Pi, as a user with sudo:
curl -fsSL https://raw.githubusercontent.com/LSinstra/OdooPIAI/claude/odoo-ai-raspberry-pi-8I4Aa/install.sh \
  | sudo bash
```

That script:

1. Installs Docker + compose plugin (if missing)
2. Clones this repo to `/opt/odoopiai`
3. Generates `.env` with strong random secrets; prompts for your Anthropic key
4. Builds + starts the stack
5. Registers two systemd units:
   - `odoopiai.service` — starts the stack on boot
   - `odoopiai-updater.timer` — every 30s, checks your branch and redeploys if it moved
6. Installs the `odoopiai` CLI (`status`, `logs`, `update`, `restart`, `url`, …)

Once it's up, visit the URL `install.sh` prints — your Tailscale IP on port 8080.

## The iteration loop (Claude Code → push → Pi auto-deploys)

```text
┌──────────────┐   git push    ┌──────────┐  systemd timer   ┌───────────┐
│  your laptop │ ────────────► │  GitHub  │ ◄─────── polls ──│    Pi     │
│ Claude Code  │               └──────────┘   every 30s      │  /opt/... │
└──────────────┘                                             └─────┬─────┘
                                                                   │ docker compose
                                                                   ▼
                                                             ┌───────────┐
                                                             │   app     │
                                                             └───────────┘
```

`scripts/auto-update.sh` pulls, then either rebuilds the image (if `Dockerfile`,
`requirements.txt`, `docker-compose.yml`, or the entrypoint changed) or just
restarts the api container (when you only changed Python/templates). Typical
cycle when iterating on prompts or routes: **~8 seconds** from `git push` to
live on Pi.

## Docs

- [`docs/RASPBERRY_PI_SETUP.md`](docs/RASPBERRY_PI_SETUP.md) — installer, filesystem layout, troubleshooting
- [`docs/TAILSCALE_ACCESS.md`](docs/TAILSCALE_ACCESS.md) — reach the Pi from anywhere
- [`docs/ODOO_SETUP.md`](docs/ODOO_SETUP.md) — how to create the Odoo API key
- [`docs/CLAUDE_CODE_WORKFLOW.md`](docs/CLAUDE_CODE_WORKFLOW.md) — iterating with Claude Code against this repo

## Architecture notes

- **Every Claude call** goes through [`app/services/claude.py`](app/services/claude.py).
  Single entry point → consistent prompt caching, token + cache-hit telemetry
  logged to `cost_logs`.
- **Context pack** built in [`app/services/context_builder.py`](app/services/context_builder.py)
  is JSON-serialized with `sort_keys=True` so the cache breakpoint stays
  stable across calls for the same project.
- **PII redaction** (emails, phones) runs on task descriptions before they're
  sent to Claude — toggle via `REDACT_PII` in `.env`.
- **Odoo API keys encrypted at rest** with Fernet (`APP_SECRET_KEY`).
- **AI-generated content is stored locally** as `insights` (with
  `(user_id, project_id, content_hash)` dedup) so the risk scanner doesn't spam
  the chatter on every run.

## License

MIT.
