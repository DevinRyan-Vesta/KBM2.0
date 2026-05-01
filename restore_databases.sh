#!/bin/bash
#
# KBM 2.0 Database Restore Script
# Restores master database and all tenant databases from a backup
#

set -e

# Configuration
BACKUP_DIR="/volume1/KBM/backups"
PROJECT_DIR="/volume1/KBM/KBM2.0"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if backup file is provided
if [ $# -eq 0 ]; then
    echo -e "${RED}Error: No backup file specified${NC}"
    echo ""
    echo "Usage: $0 <backup_file.tar.gz>"
    echo ""
    echo "Available backups:"
    ls -lh "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ", " $6 " " $7 ")"}'
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    # Try looking in the backup directory
    if [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        BACKUP_FILE="$BACKUP_DIR/$BACKUP_FILE"
    else
        echo -e "${RED}Error: Backup file not found: $BACKUP_FILE${NC}"
        exit 1
    fi
fi

echo -e "${RED}====================================${NC}"
echo -e "${RED}KBM 2.0 Database RESTORE${NC}"
echo -e "${RED}====================================${NC}"
echo -e "${YELLOW}⚠️  WARNING: This will OVERWRITE existing databases!${NC}"
echo ""
echo "Backup file: $BACKUP_FILE"
echo "Project directory: $PROJECT_DIR"
echo ""
read -p "Are you sure you want to continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Restore cancelled${NC}"
    exit 0
fi

# Create temporary restore directory
TEMP_DIR=$(mktemp -d)
echo -e "${YELLOW}Extracting backup...${NC}"
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Find the extracted backup directory
EXTRACTED_DIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "backup_*" | head -1)

if [ -z "$EXTRACTED_DIR" ]; then
    echo -e "${RED}Error: Could not find backup data in archive${NC}"
    rm -rf "$TEMP_DIR"
    exit 1
fi

echo -e "${GREEN}✓ Backup extracted${NC}"

# Stop Docker containers to prevent database locks
echo -e "${YELLOW}Stopping Docker containers...${NC}"
cd "$PROJECT_DIR"
docker-compose down
echo -e "${GREEN}✓ Containers stopped${NC}"

# Backup current databases (just in case)
SAFETY_BACKUP="/tmp/kbm_safety_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$SAFETY_BACKUP"
echo -e "${YELLOW}Creating safety backup of current databases...${NC}"
[ -f "$PROJECT_DIR/master_db/master.db" ] && cp "$PROJECT_DIR/master_db/master.db" "$SAFETY_BACKUP/"
[ -d "$PROJECT_DIR/tenant_dbs" ] && cp -r "$PROJECT_DIR/tenant_dbs" "$SAFETY_BACKUP/"
echo -e "${GREEN}✓ Safety backup created at: $SAFETY_BACKUP${NC}"

# Restore master database
echo -e "${YELLOW}Restoring master database...${NC}"
if [ -f "$EXTRACTED_DIR/master.db" ]; then
    mkdir -p "$PROJECT_DIR/master_db"
    cp "$EXTRACTED_DIR/master.db" "$PROJECT_DIR/master_db/master.db"
    echo -e "${GREEN}✓ Master database restored${NC}"
else
    echo -e "${RED}✗ Master database not found in backup!${NC}"
fi

# Restore tenant databases
echo -e "${YELLOW}Restoring tenant databases...${NC}"
TENANT_COUNT=0
mkdir -p "$PROJECT_DIR/tenant_dbs"

for db_file in "$EXTRACTED_DIR"/*.db; do
    if [ -f "$db_file" ] && [ "$(basename "$db_file")" != "master.db" ]; then
        db_name=$(basename "$db_file")
        cp "$db_file" "$PROJECT_DIR/tenant_dbs/$db_name"
        TENANT_COUNT=$((TENANT_COUNT + 1))
        echo -e "${GREEN}✓ Restored: $db_name${NC}"
    fi
done

echo -e "${GREEN}✓ Restored $TENANT_COUNT tenant database(s)${NC}"

# Clean up temporary directory
rm -rf "$TEMP_DIR"

# Start Docker containers
echo -e "${YELLOW}Starting Docker containers...${NC}"
docker-compose up -d
echo -e "${GREEN}✓ Containers started${NC}"

echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Restore Complete!${NC}"
echo -e "${GREEN}====================================${NC}"
echo "Restored from: $BACKUP_FILE"
echo "Safety backup: $SAFETY_BACKUP"
echo ""
echo "Note: Safety backup will be kept at $SAFETY_BACKUP"
echo "You can delete it manually once you've verified the restore."
