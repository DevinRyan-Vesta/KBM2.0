#!/usr/bin/env bash
# ==============================================================================
# KBM 2.0 — Migrate master_db/ and tenant_dbs/ from the NAS to this VPS.
#
# Stops the app container before copying so SQLite files are at rest, then
# starts it again. Safe to re-run; uses rsync.
#
# Usage:
#   bash deploy/migrate_from_nas.sh <user>@<nas-host>:<path-to-KBM-dir>
#
# Example (NAS path is the directory that contains master_db/ and tenant_dbs/):
#   bash deploy/migrate_from_nas.sh admin@10.0.0.50:/volume1/KBM
#
# Requires:
#   - SSH access from this VPS to the NAS (key-based auth recommended)
#   - rsync installed on both ends
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() { printf '\033[1;34m[migrate]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

[[ $# -eq 1 ]] || die "Usage: $0 <user>@<nas-host>:<path-to-KBM-dir>"
SOURCE="$1"

command -v rsync >/dev/null || die "rsync not installed (sudo apt install rsync)"
command -v docker >/dev/null || die "docker not installed"

# ------------------------------------------------------------------------------
# 1. Confirm the source actually has what we expect
# ------------------------------------------------------------------------------
log "Verifying source contains master_db/ and tenant_dbs/"
SOURCE_HOST="${SOURCE%%:*}"
SOURCE_PATH="${SOURCE#*:}"
if ! ssh -o BatchMode=yes "${SOURCE_HOST}" "test -d '${SOURCE_PATH}/master_db' && test -d '${SOURCE_PATH}/tenant_dbs'"; then
	die "Source ${SOURCE} does not contain master_db/ and tenant_dbs/ (or SSH failed)"
fi

# ------------------------------------------------------------------------------
# 2. Local backup of whatever's already on the VPS — just in case
# ------------------------------------------------------------------------------
TS="$(date +%Y%m%d_%H%M%S)"
if [[ -d master_db || -d tenant_dbs ]]; then
	BACKUP_DIR="backups/pre_migration_${TS}"
	log "Backing up existing local data to ${BACKUP_DIR}"
	mkdir -p "${BACKUP_DIR}"
	[[ -d master_db ]] && cp -a master_db "${BACKUP_DIR}/"
	[[ -d tenant_dbs ]] && cp -a tenant_dbs "${BACKUP_DIR}/"
fi

# ------------------------------------------------------------------------------
# 3. Stop app so SQLite files aren't being written during the rsync
#    Caddy can keep running.
# ------------------------------------------------------------------------------
APP_WAS_RUNNING=0
if docker compose ps --status running --services 2>/dev/null | grep -q '^python-app$'; then
	APP_WAS_RUNNING=1
	log "Stopping python-app container during copy"
	docker compose stop python-app
fi

cleanup() {
	if [[ "${APP_WAS_RUNNING}" -eq 1 ]]; then
		log "Restarting python-app container"
		docker compose start python-app || true
	fi
}
trap cleanup EXIT

# ------------------------------------------------------------------------------
# 4. rsync the SQLite files
# ------------------------------------------------------------------------------
log "Syncing master_db/"
rsync -avz --delete "${SOURCE}/master_db/" "./master_db/"

log "Syncing tenant_dbs/"
rsync -avz --delete "${SOURCE}/tenant_dbs/" "./tenant_dbs/"

# ------------------------------------------------------------------------------
# 5. Quick integrity check
# ------------------------------------------------------------------------------
if [[ -f master_db/master.db ]]; then
	log "Master DB present: $(stat -c%s master_db/master.db) bytes"
else
	warn "master_db/master.db not found after sync — check NAS path"
fi

TENANT_COUNT="$(find tenant_dbs -maxdepth 1 -name '*.db' 2>/dev/null | wc -l)"
log "Tenant DB count: ${TENANT_COUNT}"

# ------------------------------------------------------------------------------
# 6. Done — app gets restarted by trap
# ------------------------------------------------------------------------------
log "Migration complete. Verifying app comes back healthy..."
sleep 3
for i in {1..15}; do
	if docker compose exec -T python-app curl -fs http://localhost:8000/health >/dev/null 2>&1; then
		log "App healthy after migration"
		exit 0
	fi
	sleep 2
done
warn "App did not return to healthy within 30s — check: docker compose logs python-app"
