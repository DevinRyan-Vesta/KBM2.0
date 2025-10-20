# Development Workflow Guide
## Managing KBM 2.0 During Active Development

This guide covers best practices for developing and updating KBM 2.0 while it's actively deployed.

---

## Table of Contents

1. [Environment Strategy](#environment-strategy)
2. [Local Development Setup](#local-development-setup)
3. [Making and Testing Changes](#making-and-testing-changes)
4. [Deploying Updates to Production](#deploying-updates-to-production)
5. [Database Migration Strategy](#database-migration-strategy)
6. [Rollback Procedures](#rollback-procedures)
7. [Common Scenarios](#common-scenarios)
8. [Best Practices](#best-practices)

---

## Environment Strategy

### Three-Environment Approach (Recommended)

1. **Local Development** - Your workstation (fast iteration)
2. **Staging/Testing** - Mirror of production (optional but recommended)
3. **Production** - Live user-facing deployment

### Environment File Management

Keep separate environment configurations:

```
.env.development    # Local development settings
.env.staging        # Staging server settings (if you have one)
.env.production     # Production server settings
.env.example        # Template (no secrets, committed to git)
```

**Current Setup:**
- `.env` - Currently used for production
- `.env.development` - Already exists in your project
- `.env.production` - Already exists in your project

---

## Local Development Setup

### Option 1: Run Locally Without Docker (Fastest for Development)

**Advantages:**
- Instant code changes (no rebuild needed)
- Faster startup time
- Easy debugging with breakpoints
- Direct access to database files

**Setup:**

```bash
# 1. Create Python virtual environment (if not exists)
python -m venv .venv

# 2. Activate virtual environment
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Use development environment
cp .env.development .env

# 5. Run the application
python app_multitenant.py
```

**Development workflow:**
```bash
# Every time you start working:
.venv\Scripts\activate          # Activate virtual environment
python app_multitenant.py       # Run app (auto-reloads on code changes)

# Make changes to code → Save → Flask auto-reloads → Test in browser
```

**Stopping local development:**
```bash
# Press Ctrl+C to stop the server
deactivate  # Exit virtual environment
```

---

### Option 2: Docker with Volume Mounts (Good for Testing Deployment)

**Advantages:**
- Tests in production-like environment
- Catches Docker-specific issues
- Good for final testing before deployment

**Setup:**

Create `compose.dev.yaml`:

```yaml
services:
  kbm-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: kbm-app-dev
    restart: unless-stopped
    init: true
    ports:
      - "8000:8000"
    env_file:
      - .env.development
    volumes:
      # Mount code for live updates
      - ./templates:/app/templates
      - ./static:/app/static
      - .:/app
      # Persist data
      - kbm-dev-data:/app/KBM2_data
      - kbm-dev-logs:/app/logs
    command: flask run --host=0.0.0.0 --port=8000 --reload
    environment:
      - FLASK_ENV=development
      - FLASK_DEBUG=1

volumes:
  kbm-dev-data:
  kbm-dev-logs:
```

**Usage:**

```bash
# Start development Docker environment
docker-compose -f compose.dev.yaml up

# Code changes to templates/static reload automatically
# Python code changes require container restart:
docker-compose -f compose.dev.yaml restart

# Stop
docker-compose -f compose.dev.yaml down
```

---

## Making and Testing Changes

### Typical Development Workflow

```bash
# 1. Start local development server
.venv\Scripts\activate
python app_multitenant.py

# 2. Make changes to code in your editor

# 3. Flask auto-reloads - test in browser (http://localhost:5000)

# 4. When satisfied, commit changes
git add .
git commit -m "Description of changes"

# 5. Push to GitHub
git push origin main

# 6. Deploy to production (see next section)
```

### What Auto-Reloads and What Doesn't

**Auto-reloads locally (Flask development server):**
- ✅ Python code changes (.py files)
- ✅ Template changes (.html files)
- ✅ Static files (CSS, JS)

**Requires restart:**
- ❌ Environment variable changes (.env)
- ❌ Dependency changes (requirements.txt)
- ❌ Docker configuration (Dockerfile, compose.yaml)

---

## Deploying Updates to Production

### Standard Update Process

**For Code-Only Changes (No Dependencies):**

```bash
# SSH into your production server
ssh user@your-server-ip

# Navigate to project directory
cd /opt/KBM2.0  # or wherever you deployed

# Pull latest changes from GitHub
git pull origin main

# Restart Docker containers
docker-compose down
docker-compose up -d

# Monitor logs for errors
docker-compose logs -f
```

**For Changes with New Dependencies:**

```bash
# Pull changes
git pull origin main

# Rebuild Docker image (picks up new requirements.txt)
docker-compose build --no-cache

# Restart containers
docker-compose down
docker-compose up -d

# Verify
docker-compose logs -f
```

---

### Quick Update Script

Create a deployment script for easy updates:

**`deploy.sh`** (create in project root):

```bash
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
cp -r KBM2_data "$BACKUP_DIR/backup_$TIMESTAMP"
echo "✓ Backup created at $BACKUP_DIR/backup_$TIMESTAMP"

# Pull latest changes
echo "Pulling latest code from GitHub..."
git pull origin main

# Ask if rebuild is needed
read -p "Rebuild Docker image? (y/n) [n]: " REBUILD
REBUILD=${REBUILD:-n}

if [[ "$REBUILD" =~ ^[Yy]$ ]]; then
    echo "Rebuilding Docker image..."
    docker-compose build --no-cache
fi

# Restart containers
echo "Restarting containers..."
docker-compose down
docker-compose up -d

# Show logs
echo "=========================================="
echo "Deployment complete! Showing logs..."
echo "Press Ctrl+C to exit logs"
echo "=========================================="
sleep 2
docker-compose logs -f
```

**Usage:**

```bash
chmod +x deploy.sh
./deploy.sh
```

---

## Database Migration Strategy

### For Schema Changes

**When adding new tables/columns:**

1. **Create migration script** (locally):

```python
# migrations/add_new_feature.py
from utilities.master_database import master_db
from utilities.tenant_database import tenant_db

def upgrade_master():
    """Add columns to master database"""
    # Example: Add new column
    with master_db.engine.connect() as conn:
        conn.execute("ALTER TABLE accounts ADD COLUMN new_field TEXT")

def upgrade_tenant():
    """Add columns to tenant databases"""
    # Will be run for each tenant
    with tenant_db.engine.connect() as conn:
        conn.execute("ALTER TABLE items ADD COLUMN new_field TEXT")
```

2. **Test locally** with your development database

3. **Deploy to production** and run migration:

```bash
# In production
docker-compose exec kbm-app python migrations/add_new_feature.py
```

### Handling Multi-Tenant Migrations

Your app has **one master.db** and **multiple tenant databases**. When adding features:

**Template for tenant migration:**

```python
# migrate_tenants.py
from app_multitenant import create_app
from utilities.master_database import master_db, Account
import sqlite3

app = create_app()

with app.app_context():
    # Get all tenants
    accounts = Account.query.all()

    for account in accounts:
        db_path = f"KBM2_data/{account.subdomain}.db"
        print(f"Migrating {account.subdomain}...")

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Add your migration SQL here
            cursor.execute("ALTER TABLE items ADD COLUMN new_field TEXT DEFAULT ''")

            conn.commit()
            conn.close()
            print(f"✓ {account.subdomain} migrated")
        except Exception as e:
            print(f"✗ Error migrating {account.subdomain}: {e}")

print("Migration complete!")
```

---

## Rollback Procedures

### Quick Rollback (Code Only)

```bash
# View recent commits
git log --oneline -5

# Rollback to previous commit
git reset --hard HEAD~1  # Go back 1 commit
# Or specific commit:
git reset --hard abc1234

# Restart containers
docker-compose restart

# If you already pushed, force push (careful!):
git push origin main --force
```

### Full Rollback (Code + Database)

```bash
# 1. Restore database from backup
cd /opt/KBM2.0
rm -rf KBM2_data
cp -r /opt/kbm-backups/backup_20251020_140000 KBM2_data

# 2. Rollback code
git reset --hard <commit-hash>

# 3. Rebuild and restart
docker-compose down
docker-compose build
docker-compose up -d
```

### Tagged Releases (Recommended)

Before major changes, tag releases:

```bash
# Tag current stable version
git tag -a v1.0.0 -m "Stable release before new feature"
git push origin v1.0.0

# To rollback to a tag later:
git checkout v1.0.0
docker-compose down
docker-compose build
docker-compose up -d
```

---

## Common Scenarios

### Scenario 1: Fix a Bug in Production

```bash
# 1. Reproduce bug locally
python app_multitenant.py

# 2. Fix the bug in your code

# 3. Test fix locally

# 4. Commit and push
git add .
git commit -m "Fix: Description of bug fix"
git push origin main

# 5. Deploy (on production server)
cd /opt/KBM2.0
git pull origin main
docker-compose restart

# 6. Verify fix
docker-compose logs -f
```

**Timeline:** 5-10 minutes from fix to production

---

### Scenario 2: Add New Feature

```bash
# 1. Develop feature locally
# ... code changes ...

# 2. Test thoroughly locally

# 3. Create feature branch (optional but recommended)
git checkout -b feature/new-feature
git add .
git commit -m "Add: New feature description"
git push origin feature/new-feature

# 4. Merge to main when ready
git checkout main
git merge feature/new-feature
git push origin main

# 5. Deploy to production
# ... standard deployment process ...
```

---

### Scenario 3: Update Dependencies

```bash
# 1. Update requirements.txt locally
pip install new-package
pip freeze > requirements.txt

# 2. Test locally
pip install -r requirements.txt
python app_multitenant.py

# 3. Commit and push
git add requirements.txt
git commit -m "Add new-package dependency"
git push origin main

# 4. Deploy with rebuild (on production server)
cd /opt/KBM2.0
git pull origin main
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

---

### Scenario 4: Update Environment Variables

```bash
# 1. Edit .env on production server
ssh user@your-server
cd /opt/KBM2.0
nano .env  # Make changes

# 2. Restart to apply changes
docker-compose restart

# 3. Verify
docker-compose logs -f
```

---

### Scenario 5: Emergency Rollback

```bash
# Production is broken, need to rollback NOW

# 1. Check recent commits
git log --oneline -5

# 2. Rollback to last known good commit
git reset --hard <last-good-commit>

# 3. Restart
docker-compose restart

# 4. If database is affected, restore backup
cp -r /opt/kbm-backups/backup_latest/* KBM2_data/
docker-compose restart
```

---

## Best Practices

### 1. Always Backup Before Updates

```bash
# Automated in deploy.sh script, or manually:
cp -r KBM2_data /opt/kbm-backups/backup_$(date +%Y%m%d_%H%M%S)
```

### 2. Test Locally First

**Never deploy untested code to production!**

```bash
# Local testing checklist:
✓ Code runs without errors
✓ New features work as expected
✓ Existing features still work (regression testing)
✓ Database migrations tested (if applicable)
```

### 3. Use Meaningful Commit Messages

```bash
# Good examples:
git commit -m "Fix: Login CSRF token missing error"
git commit -m "Add: Bulk import for contacts"
git commit -m "Update: Improve sign swap performance"
git commit -m "Docs: Add development workflow guide"

# Bad examples:
git commit -m "fix"
git commit -m "updates"
git commit -m "wip"
```

### 4. Deploy During Low-Traffic Times

- Early morning or late evening
- Avoid peak business hours
- Notify users of planned maintenance if downtime expected

### 5. Monitor After Deployment

```bash
# Watch logs for 5-10 minutes after deployment
docker-compose logs -f

# Check for errors:
docker-compose logs | grep ERROR
docker-compose logs | grep CRITICAL
```

### 6. Keep Production and Development Separate

**Production environment variables:**
```bash
ENV=production
DEBUG=False
FLASK_DEBUG=0
```

**Development environment variables:**
```bash
ENV=development
DEBUG=True
FLASK_DEBUG=1
```

### 7. Document Major Changes

Keep a changelog:

**CHANGELOG.md:**
```markdown
# Changelog

## [Unreleased]
- Added bulk contact import feature
- Fixed sign swap validation bug

## [1.1.0] - 2025-10-20
- Added CSRF protection to all forms
- Updated deployment documentation
- Fixed Docker entrypoint line ending issues

## [1.0.0] - 2025-10-15
- Initial production deployment
```

---

## Quick Reference Commands

### Local Development

```bash
# Start local dev server
.venv\Scripts\activate
python app_multitenant.py

# Install new package
pip install package-name
pip freeze > requirements.txt
```

### Production Deployment

```bash
# Quick update (code only)
git pull origin main && docker-compose restart

# Full rebuild (new dependencies)
git pull origin main && docker-compose build --no-cache && docker-compose down && docker-compose up -d

# View logs
docker-compose logs -f

# Restart containers
docker-compose restart

# Stop everything
docker-compose down
```

### Database Operations

```bash
# Backup database
cp -r KBM2_data /opt/kbm-backups/backup_$(date +%Y%m%d_%H%M%S)

# Access SQLite database
docker-compose exec kbm-app sqlite3 /app/KBM2_data/master.db

# Run migration script
docker-compose exec kbm-app python migrations/script.py
```

### Git Operations

```bash
# Check status
git status

# View recent commits
git log --oneline -10

# Create tag
git tag -a v1.0.0 -m "Release description"
git push origin v1.0.0

# Rollback
git reset --hard <commit-hash>
```

---

## Recommended Daily Workflow

### Morning: Start Development

```bash
cd C:\Users\dryan\WorkSpaces\KBM2.0
.venv\Scripts\activate
git pull origin main  # Get latest changes
python app_multitenant.py
```

### During Day: Make Changes

```bash
# Make changes → Save → Test in browser
# Flask auto-reloads on every save
```

### Evening: Commit Progress

```bash
git add .
git commit -m "Add: Description of what you built today"
git push origin main

# Optional: Deploy to production if stable
ssh user@server "cd /opt/KBM2.0 && ./deploy.sh"
```

---

## Troubleshooting Common Issues

### "Port already in use"

```bash
# Windows - kill process on port 5000
netstat -ano | findstr :5000
taskkill /PID <PID> /F

# Or change port
flask run --port=5001
```

### "Module not found" after adding dependency

```bash
# Reinstall requirements
pip install -r requirements.txt

# Or install specific package
pip install package-name
```

### Docker container won't start

```bash
# View full logs
docker-compose logs

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Changes not appearing in production

```bash
# Verify you pulled latest code
git log -1

# Verify Docker rebuilt
docker-compose build --no-cache

# Verify container restarted
docker-compose ps

# Check container has latest code
docker-compose exec kbm-app git log -1
```

---

## Summary: Fastest Path to Updates

**For most code changes:**

1. **Local:** Edit code → Test locally
2. **Commit:** `git add . && git commit -m "Description"`
3. **Push:** `git push origin main`
4. **Deploy:** `ssh server` → `cd /opt/KBM2.0` → `git pull && docker-compose restart`

**Total time:** 2-5 minutes from code change to live in production.

---

**Last Updated:** 2025-10-20
**For:** KBM 2.0 Multi-Tenant Application
