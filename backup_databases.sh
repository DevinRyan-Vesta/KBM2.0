#!/bin/bash
#
# KBM 2.0 Database Backup Script
# Backs up master database and all tenant databases
#

set -e

# Configuration
BACKUP_DIR="/volume1/KBM/backups"
PROJECT_DIR="/volume1/KBM/KBM2.0"
RETENTION_DAYS=30
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}KBM 2.0 Database Backup${NC}"
echo -e "${GREEN}====================================${NC}"
echo "Timestamp: $(date)"
echo "Backup Directory: $BACKUP_DIR"
echo ""

# Create a dated backup subdirectory
BACKUP_SUBDIR="$BACKUP_DIR/backup_$TIMESTAMP"
mkdir -p "$BACKUP_SUBDIR"

# Backup master database
echo -e "${YELLOW}Backing up master database...${NC}"
if [ -f "$PROJECT_DIR/master_db/master.db" ]; then
    cp "$PROJECT_DIR/master_db/master.db" "$BACKUP_SUBDIR/master.db"
    echo -e "${GREEN}✓ Master database backed up${NC}"
else
    echo -e "${RED}✗ Master database not found!${NC}"
fi

# Backup tenant databases
echo -e "${YELLOW}Backing up tenant databases...${NC}"
TENANT_COUNT=0
if [ -d "$PROJECT_DIR/tenant_dbs" ]; then
    for db_file in "$PROJECT_DIR/tenant_dbs"/*.db; do
        if [ -f "$db_file" ]; then
            db_name=$(basename "$db_file")
            cp "$db_file" "$BACKUP_SUBDIR/$db_name"
            TENANT_COUNT=$((TENANT_COUNT + 1))
            echo -e "${GREEN}✓ Backed up: $db_name${NC}"
        fi
    done
else
    echo -e "${YELLOW}! No tenant databases directory found${NC}"
fi

echo -e "${GREEN}✓ Backed up $TENANT_COUNT tenant database(s)${NC}"
echo ""

# Create a compressed archive
echo -e "${YELLOW}Creating compressed archive...${NC}"
cd "$BACKUP_DIR"
tar -czf "backup_$TIMESTAMP.tar.gz" "backup_$TIMESTAMP"
ARCHIVE_SIZE=$(du -h "backup_$TIMESTAMP.tar.gz" | cut -f1)
echo -e "${GREEN}✓ Created archive: backup_$TIMESTAMP.tar.gz ($ARCHIVE_SIZE)${NC}"

# Remove uncompressed backup directory
rm -rf "$BACKUP_SUBDIR"

# Clean up old backups (older than retention period)
echo -e "${YELLOW}Cleaning up old backups (keeping last $RETENTION_DAYS days)...${NC}"
find "$BACKUP_DIR" -name "backup_*.tar.gz" -type f -mtime +$RETENTION_DAYS -delete
REMAINING=$(find "$BACKUP_DIR" -name "backup_*.tar.gz" -type f | wc -l)
echo -e "${GREEN}✓ Cleanup complete. $REMAINING backup(s) remaining${NC}"

echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}Backup Complete!${NC}"
echo -e "${GREEN}====================================${NC}"
echo "Location: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
echo "Size: $ARCHIVE_SIZE"
echo ""

# List recent backups
echo "Recent backups:"
ls -lh "$BACKUP_DIR"/backup_*.tar.gz 2>/dev/null | tail -5 | awk '{print "  " $9 " (" $5 ")"}'
