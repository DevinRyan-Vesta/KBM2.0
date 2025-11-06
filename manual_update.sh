#!/bin/bash
# Manual update script to run on the NAS via SSH
# Usage: ssh your-nas "cd /volume1/KBM/KBM2.0 && bash manual_update.sh"

set -e  # Exit on error

echo "========================================"
echo "MANUAL SYSTEM UPDATE"
echo "========================================"

cd /volume1/KBM/KBM2.0

# Step 1: Show current version
echo ""
echo "[1/4] Current Version:"
git log -1 --oneline

# Step 2: Pull latest changes
echo ""
echo "[2/4] Pulling latest changes from GitHub..."
git pull origin main

# Step 3: Rebuild the Docker image
echo ""
echo "[3/4] Rebuilding Docker image..."
docker compose build --no-cache python-app

# Step 4: Restart containers
echo ""
echo "[4/4] Restarting containers..."
docker compose down
docker compose up -d

echo ""
echo "========================================"
echo "UPDATE COMPLETED SUCCESSFULLY!"
echo "========================================"
echo ""
echo "New version:"
git log -1 --oneline
echo ""
echo "Containers:"
docker compose ps
