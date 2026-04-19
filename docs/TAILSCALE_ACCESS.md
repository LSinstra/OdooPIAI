# Reaching OdooPIAI over Tailscale

The app binds to `0.0.0.0:8080` inside the container, and `docker-compose.yml`
maps that to the host. Tailscale attaches a private IPv4 (usually
`100.x.y.z`) to the Pi — point your browser there and you're in.

## One-time

```bash
sudo tailscale up
tailscale ip -4
# → 100.83.17.42   (example)
```

From any device on your tailnet:

```
http://100.83.17.42:8080
```

## MagicDNS (nicer URLs)

Enable MagicDNS in the Tailscale admin console. Then your Pi is reachable at
`http://<pi-hostname>:8080` — e.g. `http://raspberrypi:8080`. You can also
give it a stable name via:

```bash
sudo tailscale up --hostname=odoopiai
# → http://odoopiai:8080
```

## Tailscale Funnel / Serve (HTTPS + public, optional)

If you want HTTPS without a reverse proxy on the Pi, let Tailscale terminate
TLS and proxy to the local app:

```bash
sudo tailscale serve --bg --https=443 http://localhost:8080
# → https://odoopiai.tailXXXXXX.ts.net
```

This keeps access limited to your tailnet. If you want the whole internet to
reach it (don't, unless you add auth in front), use `tailscale funnel` instead.

## ACLs

The app enforces its own login (sessions via JWT cookie), but you probably
want to narrow which devices can even reach port 8080. In the Tailscale admin
console, add an ACL like:

```jsonc
{
  "acls": [
    { "action": "accept", "src": ["group:admin"], "dst": ["tag:odoopiai:8080"] }
  ],
  "tagOwners": {
    "tag:odoopiai": ["autogroup:admin"]
  }
}
```

Then tag the Pi: `sudo tailscale up --advertise-tags=tag:odoopiai`.

## Firewall note

UFW / nftables on the Pi can block Tailscale traffic if you've hardened it.
If access fails from the tailnet but works locally, check:

```bash
sudo ufw status
sudo iptables -S | grep 8080
```

The simplest fix is to allow the Tailscale interface entirely:

```bash
sudo ufw allow in on tailscale0
```
