# Odoo 17 connection setup

OdooPIAI talks to Odoo over XML-RPC using an **API key** (not a password).
This works for Odoo.sh, Odoo Enterprise, and self-hosted instances.

## 1. Create the API key

1. In Odoo, top-right avatar → **My Profile**
2. Enable Developer Mode if needed (Settings → General → Developer Tools → Activate)
3. In your profile, open the **Account Security** tab
4. Click **New API Key**, name it `OdooPIAI`, copy it — you can't see it again

## 2. Required permissions

The user you authenticate as needs:

- `Project / User` (read/write own projects) at minimum for Plan + Ask AI
- `Project / Administrator` if you want the stakeholder drafter + risk scan
  to cover all projects
- Access to the databases you expect to manage

## 3. What to enter in Settings → Add connection

| Field    | Value                                                      |
| -------- | ---------------------------------------------------------- |
| Label    | Anything — e.g. `Production`                               |
| URL      | `https://mycompany.odoo.com` (no trailing slash)           |
| Database | From Odoo.sh dashboard or the login-page DB selector       |
| Username | Your Odoo login email                                      |
| API key  | The key you just created                                   |

OdooPIAI will call `common.authenticate` before saving — if your credentials
are bad, you'll get the error inline.

## 4. Storage

API keys are encrypted with Fernet (`APP_SECRET_KEY` in `.env`) before being
stored in Postgres. If you lose `APP_SECRET_KEY`, stored keys become
undecryptable — regenerate it only when you're OK re-adding connections.

## 5. Network

Odoo.sh endpoints are publicly reachable, so the Pi doesn't need a static IP.
If your Odoo is self-hosted and behind a VPN, put the Pi on the same VPN
(Tailscale subnet-routing works well).

## 6. Rate limits

XML-RPC on Odoo.sh has an undocumented rate limit around ~60 req/min. Our
jobs respect this:

- `list_projects(limit=15)` once per scan cycle
- One `search_read` per project per scan cycle
- One Claude call per project per scan cycle

With 15 projects and a 4-hour cadence, this stays well under the limit.
Increase `RISK_SCAN_INTERVAL_HOURS` if you have more projects.
