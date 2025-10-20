# KBM 2.0 Database Backup & Restore Guide

## Overview

The backup system creates compressed archives of all databases (master + all tenant databases) and stores them with automatic rotation.

**Location:** `/volume1/KBM/backups/`
**Retention:** 30 days (configurable)
**Format:** `.tar.gz` compressed archives

---

## Manual Backup

Run a backup anytime:

```bash
cd /volume1/KBM/KBM2.0
bash backup_databases.sh
```

**Output:**
- Creates: `/volume1/KBM/backups/backup_YYYYMMDD_HHMMSS.tar.gz`
- Shows: Number of databases backed up, archive size
- Cleans: Old backups beyond retention period

---

## Automated Backups with Cron

### Setup Daily Backups (2 AM)

```bash
# Edit crontab
crontab -e

# Add this line for daily backups at 2 AM
0 2 * * * cd /volume1/KBM/KBM2.0 && bash backup_databases.sh >> /volume1/KBM/backups/backup.log 2>&1
```

### Common Cron Schedules

```bash
# Every day at 2 AM
0 2 * * * cd /volume1/KBM/KBM2.0 && bash backup_databases.sh >> /volume1/KBM/backups/backup.log 2>&1

# Every 6 hours
0 */6 * * * cd /volume1/KBM/KBM2.0 && bash backup_databases.sh >> /volume1/KBM/backups/backup.log 2>&1

# Every Sunday at 3 AM (weekly)
0 3 * * 0 cd /volume1/KBM/KBM2.0 && bash backup_databases.sh >> /volume1/KBM/backups/backup.log 2>&1
```

### Verify Cron Job

```bash
# List current cron jobs
crontab -l

# Check backup log
tail -f /volume1/KBM/backups/backup.log
```

---

## Restore from Backup

### List Available Backups

```bash
ls -lh /volume1/KBM/backups/backup_*.tar.gz
```

### Restore a Specific Backup

```bash
cd /volume1/KBM/KBM2.0

# Restore using full path
bash restore_databases.sh /volume1/KBM/backups/backup_20251020_020000.tar.gz

# Or just the filename (looks in backup directory)
bash restore_databases.sh backup_20251020_020000.tar.gz
```

**The restore script will:**
1. Ask for confirmation (type `yes`)
2. Stop Docker containers
3. Create a safety backup of current databases
4. Restore databases from backup
5. Restart Docker containers

**Safety backup location:** `/tmp/kbm_safety_backup_YYYYMMDD_HHMMSS/`

---

## What Gets Backed Up

- **Master Database:** `master_db/master.db`
  - App admin accounts
  - Tenant account records
  - Account metadata

- **Tenant Databases:** `tenant_dbs/*.db`
  - All company/tenant databases
  - User data, properties, smartlocks, etc.

---

## Configuration

Edit `backup_databases.sh` to customize:

```bash
BACKUP_DIR="/volume1/KBM/backups"      # Where backups are stored
RETENTION_DAYS=30                       # How long to keep backups
```

---

## Best Practices

### Regular Testing
```bash
# Test restore process monthly (in a test environment)
bash restore_databases.sh backup_latest.tar.gz
```

### Off-Site Backups

**Option 1: Copy to another NAS/server**
```bash
# Add to cron after backup runs
rsync -avz /volume1/KBM/backups/ user@remote-server:/backups/kbm/
```

**Option 2: Cloud backup (Backblaze, AWS S3, etc.)**
```bash
# Using rclone (install first)
rclone sync /volume1/KBM/backups/ remote:kbm-backups
```

### Monitor Backups

Create a simple monitoring script:

```bash
#!/bin/bash
# Check if backup is recent (within 25 hours)
LATEST_BACKUP=$(ls -t /volume1/KBM/backups/backup_*.tar.gz | head -1)
BACKUP_AGE=$(($(date +%s) - $(stat -c %Y "$LATEST_BACKUP")))

if [ $BACKUP_AGE -gt 90000 ]; then
    echo "WARNING: Latest backup is older than 25 hours!"
    # Send alert (email, webhook, etc.)
fi
```

---

## Troubleshooting

### Backup fails with "Permission denied"

```bash
# Make scripts executable
chmod +x backup_databases.sh restore_databases.sh

# Check directory permissions
ls -la /volume1/KBM/backups/
```

### Cron job not running

```bash
# Check if cron service is running
sudo systemctl status cron

# Check system logs
grep CRON /var/log/syslog | tail -20

# Check backup log
cat /volume1/KBM/backups/backup.log
```

### Restore doesn't work

```bash
# Verify backup archive is valid
tar -tzf /volume1/KBM/backups/backup_20251020_020000.tar.gz

# Check if Docker is stopped
docker-compose ps
```

---

## Disaster Recovery

If you need to restore on a new server:

1. **Install Docker and Docker Compose**
2. **Clone repository:**
   ```bash
   cd /volume1/KBM
   git clone https://github.com/DevinRyan-Vesta/KBM2.0.git
   ```

3. **Copy backup file to server**
4. **Restore:**
   ```bash
   cd /volume1/KBM/KBM2.0
   bash restore_databases.sh /path/to/backup.tar.gz
   ```

5. **Configure .env file**
6. **Start application:**
   ```bash
   docker-compose up -d
   ```

---

## Quick Reference

```bash
# Manual backup
bash backup_databases.sh

# List backups
ls -lh /volume1/KBM/backups/backup_*.tar.gz

# Restore
bash restore_databases.sh backup_20251020_020000.tar.gz

# Setup daily backups at 2 AM
crontab -e
# Add: 0 2 * * * cd /volume1/KBM/KBM2.0 && bash backup_databases.sh >> /volume1/KBM/backups/backup.log 2>&1

# Check cron jobs
crontab -l

# View backup log
tail -f /volume1/KBM/backups/backup.log
```
