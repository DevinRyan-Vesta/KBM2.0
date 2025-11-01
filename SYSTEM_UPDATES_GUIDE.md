# System Updates UI Guide

## Overview

The System Updates UI provides a web-based interface for managing application updates on your deployed instance. No more command line typing!

## Features

### 1. **Check for Updates**
- View current version (git commit hash, date, message)
- Check for available updates from GitHub with one click
- See list of all pending commits

### 2. **One-Click Updates**
- **Update Now**: Pull latest code and restart containers
- **Update + Rebuild**: Pull code, rebuild Docker images, and restart (use when requirements.txt changes)

### 3. **Container Management**
- View status of all Docker containers
- Restart containers without updating
- Real-time status monitoring

### 4. **System Logs**
- View recent Docker Compose logs
- Auto-refresh every 10 seconds
- Download logs as text file

### 5. **Automatic Backups**
- Database backups created before each update
- Stored in `/opt/kbm-backups`
- Timestamped for easy identification

## How to Access

1. Log in as an **App Admin** (must have app_admin role)
2. Navigate to root domain (e.g., `http://yourdomain.com:8080`)
3. Click **"System Updates"** in the Quick Actions section

## Update Process

### Quick Update (Code Changes Only)
```
1. Click "Check for Updates"
2. Review available updates
3. Click "Update Now"
4. Wait for confirmation
5. Application automatically reloads
```

### Full Update (With Dependencies)
Use "Update + Rebuild" when:
- `requirements.txt` has changed
- Dockerfile has been modified
- New system dependencies added

```
1. Click "Check for Updates"
2. Review available updates
3. Click "Update + Rebuild"
4. Wait 2-5 minutes for rebuild
5. Application automatically reloads
```

## Update Sequence

The system performs these steps automatically:

1. **Backup**: Creates backup of `master_db` and `tenant_dbs`
2. **Pull**: Fetches latest code from GitHub
3. **Rebuild** (optional): Rebuilds Docker images
4. **Restart**: Restarts all containers
5. **Health Check**: Verifies application is running

## Safety Features

- **Automatic Backups**: All databases backed up before update
- **Confirmation Dialogs**: Prevents accidental updates
- **Status Monitoring**: Real-time feedback during update
- **Error Handling**: Clear error messages if update fails

## Rollback

If an update fails, you can manually rollback:

### Option 1: Via UI
1. View logs to identify issue
2. Click "Restart Containers" (may fix transient issues)

### Option 2: Via SSH (if UI unavailable)
```bash
cd /opt/kbm2.0  # or your installation directory
git reset --hard HEAD~1
docker compose restart
```

### Option 3: Restore from Backup
```bash
cd /opt/kbm2.0
# List backups
ls -la /opt/kbm-backups

# Restore specific backup
rm -rf master_db tenant_dbs
cp -r /opt/kbm-backups/backup_YYYYMMDD_HHMMSS/master_db ./
cp -r /opt/kbm-backups/backup_YYYYMMDD_HHMMSS/tenant_dbs ./

docker compose restart
```

## Troubleshooting

### "Check for Updates" button not working
- Ensure you're logged in as app admin
- Check container status - python-app must be running
- Verify git is accessible from container

### Update hangs or times out
- Check system resources (disk space, memory)
- View logs for specific error messages
- Try "Restart Containers" first

### "Permission denied" errors
- Check file permissions on host
- Ensure Docker has access to repository directory
- Verify user running containers has correct permissions

### Cannot access UI after update
1. SSH into your NAS
2. Check container status: `docker compose ps`
3. View logs: `docker compose logs`
4. Restart if needed: `docker compose restart`

## Files Created

- **utilities/system_update.py**: Core update functionality
- **app_admin/routes.py**: Web endpoints (appended)
- **templates/app_admin/system_updates.html**: UI template
- **templates/app_admin/dashboard.html**: Updated with link

## Security

- **App Admin Only**: Only users with `app_admin` role can access
- **Root Domain Only**: Must access from root domain (not tenant subdomain)
- **CSRF Protection**: All POST requests protected with CSRF tokens
- **Confirmation Required**: Updates require explicit confirmation

## Best Practices

1. **Check logs before updating**: Look for any existing issues
2. **Note current version**: Record current commit hash before updating
3. **Update during low traffic**: Perform updates when few users are online
4. **Test after update**: Verify key functionality works after update
5. **Keep backups**: Backups auto-created but verify they're working

## Command Line Alternative

The old `deploy.sh` script still works if you prefer command line:

```bash
ssh into-nas
cd /opt/kbm2.0
./deploy.sh
```

But the UI is much easier! 🎉
