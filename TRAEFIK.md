# Traefik support

KBM ships with **Caddy** as the default reverse proxy. **Traefik v3** is a
drop-in alternative — same routing, same Let's Encrypt cert issuance, same
multi-tenant subdomain gating via `/_internal/check-domain`.

You pick which proxy runs by setting `COMPOSE_FILE` in `.env`:

```
# Default (Caddy) — no setting needed
# COMPOSE_FILE is unset, docker compose uses compose.yaml only.

# Switch to Traefik:
COMPOSE_FILE=compose.yaml:compose.traefik.yaml
```

Compose merges both files when both are listed. `compose.traefik.yaml`
disables Caddy (puts it behind an unused profile) and defines a `traefik`
service. The python-app service keeps its Traefik labels from `compose.yaml`
regardless of which proxy runs — they're inert under Caddy.

## Why you might want Traefik instead of Caddy

You wouldn't, for most setups. Caddy's `on_demand_tls.ask` mechanism is
genuinely nice for multi-tenant. Pick Traefik when:

- You already run Traefik for other apps and want one proxy across them.
- You need a feature Traefik has and Caddy doesn't (advanced middlewares,
  Prometheus metrics, specific cert provider).
- You want a DNS-01 **wildcard cert** for `*.${BASE_DOMAIN}` instead of
  per-subdomain HTTP-01 certs (see below).

## Switching from Caddy to Traefik

On your VPS:

1. Pull the latest code.
2. Edit `.env`, uncomment the line:
   ```
   COMPOSE_FILE=compose.yaml:compose.traefik.yaml
   ```
3. `docker compose -p kbm down` (cleanly stops Caddy).
4. `docker compose -p kbm up -d` (starts python-app + Traefik).
5. Browse to your root domain. Watch `docker logs traefik -f` on the first
   hit — you should see an ACME challenge fire and a cert get issued.

To switch back to Caddy: comment out `COMPOSE_FILE`, then `down` + `up -d`
again.

## Cert challenge: HTTP-01 vs DNS-01 wildcard

Out of the box `traefik/traefik.yml` is configured for the **HTTP-01**
challenge. This works without any DNS provider creds, but Traefik issues
**one cert per unique subdomain** that hits the proxy. Let's Encrypt's
hard limit is 50 certs per registered domain per week.

The `tenant-gate` forwardauth middleware (defined as a label on
`python-app` in `compose.yaml`) gates per-request authorization — returns
401 for subdomains that don't map to active tenants. **It doesn't gate
cert issuance** — Traefik will still attempt LE for any subdomain that
resolves to your VPS and hits port 443. An attacker controlling a
wildcard DNS record pointed at your IP could exhaust your rate limit.

For a public multi-tenant production deployment, **switch to DNS-01 with
a wildcard cert** covering `*.${BASE_DOMAIN}`. One cert covers all
current and future tenants. No per-subdomain issuance, no rate-limit risk.

### Enabling DNS-01 wildcard (Cloudflare example)

1. Move your DNS to Cloudflare (or any provider supported by lego/Traefik).
   Create an API token with `Zone:DNS:Edit` on the `BASE_DOMAIN` zone.
2. Add to `.env`:
   ```
   CLOUDFLARE_DNS_API_TOKEN=<your token>
   ```
3. Edit `traefik/traefik.yml`. Replace the `httpChallenge:` block under
   `certificatesResolvers.letsencrypt.acme` with:
   ```yaml
   dnsChallenge:
     provider: cloudflare
     resolvers:
       - "1.1.1.1:53"
       - "8.8.8.8:53"
   ```
4. Edit `compose.traefik.yaml`, add an `environment:` block to the
   `traefik` service:
   ```yaml
   environment:
     - CLOUDFLARE_DNS_API_TOKEN=${CLOUDFLARE_DNS_API_TOKEN}
   ```
5. `docker compose -p kbm restart traefik`. Watch the logs — Traefik will
   request a wildcard cert via DNS-01 challenge.

For other providers (Route 53, Hetzner, DigitalOcean, etc.), see
<https://doc.traefik.io/traefik/https/acme/#providers>. Each provider
needs slightly different env vars.

## How the routing labels work

Every router rule lives as a label on the `python-app` service in
`compose.yaml`. They're inert when Caddy is the proxy (Caddy doesn't read
Docker labels), and active when Traefik runs.

- `kbm-root` router → matches `BASE_DOMAIN` and `www.BASE_DOMAIN` exactly.
- `kbm-tenants` router → matches any single-level subdomain via
  `HostRegexp(`^[a-z0-9-]+\.${BASE_DOMAIN}$`)`. Per-request gated by the
  `tenant-gate@docker` middleware (forwardauth → `/_internal/check-domain`).

The `/_internal/check-domain` endpoint reads the candidate host from:

1. `?domain=` query param (Caddy's `on_demand_tls.ask` passes this way)
2. `X-Forwarded-Host` header (Traefik forwardauth populates this)
3. `Host` header (fallback)

Same endpoint, both proxies, no code branching.

## Files added by this feature

```
compose.traefik.yaml         — Override file that swaps Caddy → Traefik
traefik/traefik.yml          — Traefik v3 static config (entrypoints, providers, cert resolver)
traefik/letsencrypt/         — Bind-mount target for acme.json (cert state)
                                acme.json itself is .gitignored
TRAEFIK.md                   — This file
```

## Backward compatibility

Existing deploys with `.env` files that don't set `COMPOSE_FILE` continue
to use `compose.yaml` exactly as before. The new Traefik labels on the
python-app service are inert under Caddy. No migration steps needed.
