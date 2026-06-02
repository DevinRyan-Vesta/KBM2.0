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

## Cert challenge: DNS-01 wildcard (required for multi-tenant)

`traefik/traefik.yml` is configured for the **DNS-01** challenge and issues
a single **wildcard cert** covering `*.${BASE_DOMAIN}`. This is required,
not optional, for this app:

- Tenants live on arbitrary, dynamically created subdomains
  (`<tenant>.${BASE_DOMAIN}`), matched by the `kbm-tenants` `HostRegexp`
  router.
- **Traefik has no on-demand TLS** (Caddy's killer multi-tenant feature).
  It must know cert domains up front and *cannot derive a hostname from a
  regex*. So the tenant router requests a wildcard.
- **Let's Encrypt only issues wildcards over DNS-01** — HTTP-01 cannot.
  (The original Traefik labels asked for a wildcard while the resolver was
  still on HTTP-01; that mismatch meant the ACME order failed and every
  tenant subdomain got Traefik's self-signed default cert — the "Not
  secure" bug. DNS-01 is the fix.)

One wildcard cert covers all current and future tenants — no per-subdomain
issuance, no Let's Encrypt rate-limit risk.

The `tenant-gate` forwardauth middleware still gates each *request* (401/404
for subdomains that don't map to an active tenant); the wildcard cert covers
TLS, the middleware covers authorization.

### DNS-01 is configured for Namecheap

`buywithvesta.com` uses **Namecheap** DNS, so the resolver uses the lego
`namecheap` provider. One-time setup in the Namecheap dashboard:

1. **Enable API access**: Profile → Tools → Namecheap API Access.
2. **Whitelist the VPS public IP** in that same API settings page —
   Namecheap rejects API calls from non-whitelisted IPs, which would make
   every cert request fail.
3. The `BASE_DOMAIN` zone must use **Namecheap BasicDNS** (their default
   nameservers) so the API can write the `_acme-challenge` TXT record.

Then add to `.env`:
```
NAMECHEAP_API_USER=<your Namecheap username>
NAMECHEAP_API_KEY=<API key from the API Access page>
# Optional, raise if propagation is slow (seconds):
# NAMECHEAP_PROPAGATION_TIMEOUT=1800
```

`compose.traefik.yaml` already passes these to the `traefik` container, and
`traefik/traefik.yml` already selects `provider: namecheap`. Just fill in
`.env` and `docker compose -p kbm up -d`. Watch `docker logs traefik -f` —
you should see a DNS-01 challenge and a wildcard cert get issued.

### Using a different DNS provider

If you ever move DNS off Namecheap, change `provider:` in
`traefik/traefik.yml`, swap the credential vars in `.env` +
`compose.traefik.yaml`, and consult
<https://doc.traefik.io/traefik/https/acme/#providers> for that provider's
required env vars.

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
