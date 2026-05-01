#!/bin/bash
set -e

echo "=========================================="
echo "KBM 2.0 Production Deployment"
echo "=========================================="

# Backup database before update
echo "Creating database backup..."
BACKUP_DIR="/opt/kbm-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# Backup all databases
if [ -d "KBM2_data" ]; then
    cp -r KBM2_data "$BACKUP_DIR/backup_$TIMESTAMP"
    echo "✓ Backup created at $BACKUP_DIR/backup_$TIMESTAMP"
else
    echo "⚠ No KBM2_data directory found, skipping backup"
fi

# Show current version
echo ""
echo "Current version:"
git log -1 --oneline

# Pull latest changes
echo ""
echo "Pulling latest code from GitHub..."
git fetch origin
git log HEAD..origin/main --oneline

if [ -z "$(git log HEAD..origin/main --oneline)" ]; then
    echo "Already up to date!"
    exit 0
fi

git pull origin main

echo ""
echo "New version:"
git log -1 --oneline

# Ask if rebuild is needed
echo ""
read -p "Rebuild Docker image? (needed if requirements.txt changed) (y/n) [n]: " REBUILD
REBUILD=${REBUILD:-n}

if [[ "$REBUILD" =~ ^[Yy]$ ]]; then
    echo "Rebuilding Docker image..."
    docker-compose build --no-cache
fi

# Restart containers
echo ""
echo "Restarting containers..."
docker-compose down
docker-compose up -d

# Wait for startup
echo ""
echo "Waiting for application to start..."
sleep 5

# Health check
echo ""
echo "Running health check..."
if curl -f -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "✓ Application is healthy!"
else
    echo "✗ Health check failed!"
    echo ""
    echo "Rolling back..."
    git reset --hard HEAD~1
    docker-compose restart
    echo "Rollback complete. Check logs:"
    docker-compose logs --tail=50
    exit 1
fi

# Show logs
echo ""
echo "=========================================="
echo "Deployment complete! Showing recent logs..."
echo "Press Ctrl+C to exit"
echo "=========================================="
echo ""
docker-compose logs --tail=30 -f
