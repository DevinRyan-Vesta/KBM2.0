#!/usr/bin/env bash
# ==============================================================================
# KBM 2.0 — One-shot installer for Ubuntu VPS (Hostinger or similar)
#
# Idempotent. Run as the user that will own the deployment (NOT root unless
# that user is in the docker group). Re-running only re-applies missing pieces.
#
# Usage:
#   bash deploy/install_vps.sh
# ==============================================================================
set -euo pipefail

# Resolve repo root regardless of cwd at invocation
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# ------------------------------------------------------------------------------
# 1. Sanity checks
# ------------------------------------------------------------------------------
log "Verifying Ubuntu + Docker prerequisites"

[[ -f /etc/os-release ]] || die "Cannot find /etc/os-release — is this Ubuntu?"
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || warn "Detected ${ID:-unknown} — script is tuned for Ubuntu"

command -v docker >/dev/null 2>&1 || die "docker not installed"
docker compose version >/dev/null 2>&1 || die "docker compose v2 plugin not installed"
docker info >/dev/null 2>&1 || die "current user cannot run docker — add to docker group: sudo usermod -aG docker \$USER && newgrp docker"

DOCKER_GID="$(getent group docker | cut -d: -f3 || true)"
[[ -n "${DOCKER_GID}" ]] || die "no 'docker' group on this host"
log "Detected host docker GID = ${DOCKER_GID}"

# ------------------------------------------------------------------------------
# 2. Firewall (only if ufw is present and active — don't enable it if user
#    hasn't already, to avoid locking out their SSH session unexpectedly)
# ------------------------------------------------------------------------------
if command -v ufw >/dev/null 2>&1; then
	if sudo ufw status | grep -q "Status: active"; then
		log "UFW active — ensuring 22/80/443 are allowed"
		sudo ufw allow 22/tcp >/dev/null
		sudo ufw allow 80/tcp >/dev/null
		sudo ufw allow 443/tcp >/dev/null
		sudo ufw allow 443/udp >/dev/null  # HTTP/3
	else
		warn "UFW present but inactive — skipping firewall config (enable it manually if desired)"
	fi
fi

# ------------------------------------------------------------------------------
# 3. Generate .env from template if it doesn't exist
# ------------------------------------------------------------------------------
if [[ -f .env ]]; then
	log ".env already exists — leaving it alone"
else
	[[ -f .env.production.template ]] || die ".env.production.template missing from repo"
	log "Generating .env from .env.production.template"

	SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
	INTERNAL_API_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"

	# Copy template, then substitute placeholders.
	cp .env.production.template .env
	sed -i "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET_KEY}|" .env
	sed -i "s|^INTERNAL_API_SECRET=.*|INTERNAL_API_SECRET=${INTERNAL_API_SECRET}|" .env
	sed -i "s|^DOCKER_GID=.*|DOCKER_GID=${DOCKER_GID}|" .env

	chmod 600 .env
	log "Wrote .env (mode 600) — review BASE_DOMAIN / SERVER_NAME / ACME_EMAIL before starting"
fi

# Always make sure DOCKER_GID matches the host (might differ if VPS was rebuilt)
if grep -q "^DOCKER_GID=" .env; then
	current_gid="$(grep "^DOCKER_GID=" .env | cut -d= -f2)"
	if [[ "${current_gid}" != "${DOCKER_GID}" ]]; then
		warn "Updating DOCKER_GID in .env: ${current_gid} -> ${DOCKER_GID}"
		sed -i "s|^DOCKER_GID=.*|DOCKER_GID=${DOCKER_GID}|" .env
	fi
fi

# ------------------------------------------------------------------------------
# 4. Required directories (gitignored, so won't exist on a fresh clone)
# ------------------------------------------------------------------------------
log "Ensuring data directories exist"
mkdir -p master_db tenant_dbs backups logs

# ------------------------------------------------------------------------------
# 5. Sanity-check the env values that need human input
# ------------------------------------------------------------------------------
. .env
for required in BASE_DOMAIN SERVER_NAME ACME_EMAIL SECRET_KEY INTERNAL_API_SECRET; do
	val="${!required:-}"
	if [[ -z "${val}" || "${val}" == *"__GENERATE_ME__"* || "${val}" == *"example.com"* ]]; then
		die "${required} in .env is empty or still a placeholder — edit .env and re-run"
	fi
done

# Cheap DNS sanity check — non-fatal, just informative.
if command -v getent >/dev/null 2>&1; then
	if ! getent hosts "${BASE_DOMAIN}" >/dev/null 2>&1; then
		warn "${BASE_DOMAIN} does not resolve from this VPS — Let's Encrypt will fail until DNS is set"
	fi
fi

# ------------------------------------------------------------------------------
# 6. Build & start
# ------------------------------------------------------------------------------
log "Building app image"
docker compose build

log "Starting containers"
docker compose up -d

log "Waiting for app health"
for i in {1..30}; do
	if docker compose exec -T python-app curl -fs http://localhost:8000/health >/dev/null 2>&1; then
		log "App is healthy"
		break
	fi
	sleep 2
	if [[ $i -eq 30 ]]; then
		warn "App did not respond to /health within 60s — check: docker compose logs python-app"
	fi
done

# ------------------------------------------------------------------------------
# 7. Done
# ------------------------------------------------------------------------------
cat <<EOF

============================================================
KBM 2.0 install complete.
============================================================

Next steps:
  1. Point DNS at this VPS:
       A     ${BASE_DOMAIN:-buywithvesta.com}      -> $(curl -s ifconfig.me 2>/dev/null || echo '<this-vps-ip>')
       A     *.${BASE_DOMAIN:-buywithvesta.com}    -> $(curl -s ifconfig.me 2>/dev/null || echo '<this-vps-ip>')
       (or use a CNAME for www -> ${BASE_DOMAIN:-buywithvesta.com})

  2. Migrate data from the NAS:
       bash deploy/migrate_from_nas.sh user@nas-host:/path/to/KBM

  3. Create the first app admin (if fresh install, no migration):
       docker compose exec python-app python create_app_admin.py

  4. Tail logs:
       docker compose logs -f
EOF
