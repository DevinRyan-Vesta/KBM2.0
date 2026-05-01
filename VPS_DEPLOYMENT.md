# KBM 2.0 — Hostinger / Ubuntu VPS Deployment

End-to-end guide for moving KBM 2.0 off the Synology NAS and onto a fresh
Ubuntu VPS (Hostinger or similar). Replaces the old `NAS_DEPLOYMENT.md` and
`CLOUDFLARE_TUNNEL_SETUP.md` workflows.

The new stack:

- **Caddy** (replaces nginx) — handles TLS termination with automatic
  Let's Encrypt certs, including per-tenant subdomain certs issued **on demand**.
  No wildcard cert, no DNS API plugin, no Cloudflare tunnel.
- **App** — same Flask / Gunicorn container, with a small new endpoint
  (`/_internal/check-domain`) that Caddy queries to confirm a subdomain belongs
  to a real tenant before issuing a cert.

---

## Prerequisites

On the VPS:

- Ubuntu 22.04+ (any recent LTS)
- Docker Engine + Compose v2 plugin (Hostinger's "Docker" template ships with both)
- A non-root user in the `docker` group
- Ports **80**, **443**, **22** reachable (Hostinger firewall + UFW if enabled)

Off the VPS:

- DNS control for `buywithvesta.com`
- SSH access from the VPS to the NAS (key-based) for the data migration step

---

## Step 1 — Point DNS at the VPS

At your DNS provider:

```
A     buywithvesta.com       -> <VPS public IP>
A     *.buywithvesta.com     -> <VPS public IP>
A     www.buywithvesta.com   -> <VPS public IP>   (optional; CNAME also fine)
```

The wildcard is **required** — every tenant gets `<subdomain>.buywithvesta.com`,
and Let's Encrypt needs DNS to resolve before it'll issue a cert.

If DNS still lives at Cloudflare, set those records to **DNS only** (grey cloud),
not proxied. Caddy needs to see the real client IP and terminate TLS itself.

> The current production cert via Cloudflare Tunnel will keep working until you
> cut DNS over. Plan to flip DNS during a quiet window so the cert handoff and
> session loss are contained.

---

## Step 2 — Get the code on the VPS

```bash
sudo mkdir -p /opt/kbm && sudo chown "$USER":"$USER" /opt/kbm
cd /opt/kbm
git clone https://github.com/<your-org>/<your-repo>.git .
```

(Use SSH URL if the repo is private and you have a deploy key on the VPS.)

---

## Step 3 — Run the installer

```bash
bash deploy/install_vps.sh
```

What it does:

1. Verifies Docker + Compose are available and your user can run them.
2. Detects the host's `docker` group GID (used by `compose.yaml`'s `group_add`).
3. Generates `.env` from `.env.production.template` with **fresh** `SECRET_KEY`
   and `INTERNAL_API_SECRET` values.
4. Creates `master_db/`, `tenant_dbs/`, `backups/`, `logs/`.
5. If UFW is active, opens 22 / 80 / 443.
6. `docker compose build && docker compose up -d`.
7. Polls `/health` until the app responds.

**Before it builds, edit `.env`** if you need to change `BASE_DOMAIN`,
`SERVER_NAME`, or `ACME_EMAIL` (defaults assume `buywithvesta.com`). The script
will refuse to continue if any required value is still a placeholder.

The old `.env.production` that was committed to the repo had a `SECRET_KEY`
in plain text. That key is considered **compromised** — a fresh one is generated
here. All NAS sessions will be invalidated when you cut over; users re-login.

---

## Step 4 — Migrate data from the NAS

Once the app is running with an empty database, pull the live data over:

```bash
bash deploy/migrate_from_nas.sh admin@<nas-ip>:/volume1/KBM
```

The path argument is the directory on the NAS that contains `master_db/` and
`tenant_dbs/` (i.e. the project root on the NAS).

The script:

1. SSHes to the NAS and confirms both directories exist.
2. Backs up whatever's already on the VPS to `backups/pre_migration_<ts>/`.
3. Stops the `python-app` container so SQLite isn't being written.
4. `rsync`s `master_db/` and `tenant_dbs/` from the NAS to the VPS.
5. Restarts the app and waits for `/health` to come back green.

You can re-run it any time — for example, to do a final delta-sync right before
the DNS cutover.

---

## Step 5 — Cut DNS over

After the migration:

1. Visit `https://<some-tenant>.buywithvesta.com` from a machine that resolves
   DNS to the new VPS (override `/etc/hosts` if you want to test before the
   cutover).
2. Watch Caddy issue the cert: `docker compose logs -f caddy` — you should see
   `obtained certificate` for both the apex and the test subdomain.
3. Once you're satisfied, flip DNS publicly. Existing browser sessions on the
   NAS will be invalidated by the new `SECRET_KEY` and users re-login.
4. Tear down the NAS deployment when ready.

---

## Operational reference

### Common commands

```bash
docker compose ps                    # status
docker compose logs -f python-app    # app logs
docker compose logs -f caddy         # cert issuance, proxy errors
docker compose restart python-app    # restart just the app
docker compose down && docker compose up -d   # full restart
```

### Code updates

The repo is mounted into the container, and the in-app system-update feature
(`utilities/system_update.py`) does `git pull` + `docker compose restart`
itself. The container has the docker socket mounted and is added to the host's
docker group via `compose.yaml`'s `group_add`, so this still works on Ubuntu.

For a manual update:

```bash
git pull
docker compose build python-app    # only if requirements.txt changed
docker compose up -d
```

### Backups

Database backups go to `./backups/` on the VPS. To pull them locally:

```bash
rsync -avz vps:/opt/kbm/backups/ ./local-backups/
```

The migration script also creates a one-off backup at
`backups/pre_migration_<timestamp>/`.

### TLS certs

Caddy stores certs in the `caddy_data` named volume. They survive container
restarts and rebuilds. To inspect:

```bash
docker compose exec caddy ls /data/caddy/certificates/acme-v02.api.letsencrypt.org-directory/
```

### Adding a new tenant

Create the tenant in the app admin UI as usual. The first time someone visits
`<new-subdomain>.buywithvesta.com`, Caddy will:

1. See the new SNI name.
2. Call `http://python-app:8000/_internal/check-domain?secret=...&domain=<new-subdomain>.buywithvesta.com`.
3. App confirms the tenant exists and is active → Caddy issues a Let's Encrypt
   cert.

No restart, no config edit. The first request after tenant creation may take a
few seconds while the cert is issued.

---

## Troubleshooting

**Caddy logs show `decision_func: ... not allowed`**
The `/_internal/check-domain` endpoint returned non-200. Either the subdomain
isn't in the master DB, the tenant's `status` isn't `active`, or
`INTERNAL_API_SECRET` in the Caddyfile env doesn't match `.env`. Both processes
read the same `.env`, so the most common cause is a fresh `.env` not picked up
by a running Caddy — `docker compose up -d` after editing.

**Browser shows cert error / `ERR_CERT_AUTHORITY_INVALID`**
DNS for that subdomain hasn't propagated, or Let's Encrypt is rate-limited
(50 certs / week per registered domain — unlikely unless something's looping).
Check `docker compose logs caddy | grep -i error`.

**App container can't talk to docker socket**
The host docker GID changed (rare, e.g. after a Docker reinstall). Re-run
`bash deploy/install_vps.sh` — it re-detects the GID and updates `.env`.

**`/health` returns 500 after migration**
Likely a schema mismatch between the migrated DBs and the app code. Run
migrations: `docker compose exec python-app python -m flask db upgrade -d migrations_master`.
