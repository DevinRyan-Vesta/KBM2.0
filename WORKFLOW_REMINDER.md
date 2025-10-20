# Development Workflow Reminder

## 📁 Directory Structure

You have **two KBM2.0 directories**:

1. **WORKSPACE** (Primary Development): `C:\Users\dryan\WorkSpaces\KBM2.0`
   - ✅ **Work here by default**
   - This is where you make changes
   - Where you commit to GitHub

2. **CLONED REPO** (Deployment Testing): `C:\Users\dryan\KBM2.0`
   - Used for Docker deployment testing
   - Pull changes FROM workspace when needed
   - Don't make changes here directly

---

## ✅ Correct Workflow

### Daily Development

```bash
# 1. Always start in WORKSPACE
cd C:\Users\dryan\WorkSpaces\KBM2.0

# 2. Make your code changes in VS Code
#    (edit files, add features, fix bugs)

# 3. Test locally (optional)
python app_multitenant.py

# 4. Commit changes
git add .
git commit -m "Description of changes"

# 5. Push to GitHub
git push origin main
```

### Testing Docker Deployment

When you want to test Docker deployment:

```bash
# 1. Pull changes to cloned repo
cd C:\Users\dryan\KBM2.0
git pull origin main

# 2. Fix line endings if needed (Windows issue)
sed -i 's/\r$//' entrypoint.sh

# 3. Rebuild and run Docker
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# 4. Check logs
docker-compose logs -f
```

---

## 🚫 Avoid This

**DON'T make changes in the cloned repo** (`C:\Users\dryan\KBM2.0`)

If you accidentally do:
1. Copy the files to workspace: `cp file.py /c/Users/dryan/WorkSpaces/KBM2.0/`
2. Reset the cloned repo: `cd /c/Users/dryan/KBM2.0 && git reset --hard origin/main`
3. Commit from workspace instead

---

## 📋 Quick Reference

| Task | Location | Command |
|------|----------|---------|
| **Edit Code** | Workspace | Open in VS Code |
| **Commit Changes** | Workspace | `git add . && git commit -m "..."` |
| **Push to GitHub** | Workspace | `git push origin main` |
| **Test Docker** | Cloned Repo | `git pull && docker-compose build && docker-compose up -d` |
| **View Logs** | Cloned Repo | `docker-compose logs -f` |
| **Create Admin** | Cloned Repo | `docker-compose exec python-app python create_app_admin.py` |

---

## 🔄 Full Cycle Example

**Scenario**: You want to add a new feature and deploy it

```bash
# Step 1: Develop in WORKSPACE
cd C:\Users\dryan\WorkSpaces\KBM2.0

# Step 2: Make your changes
# (edit files in VS Code)

# Step 3: Commit and push
git add .
git commit -m "Add new feature: XYZ"
git push origin main

# Step 4: Deploy to Docker for testing
cd C:\Users\dryan\KBM2.0
git pull origin main
sed -i 's/\r$//' entrypoint.sh  # Fix Windows line endings
docker-compose down
docker-compose build --no-cache
docker-compose up -d
docker-compose logs -f

# Step 5: Test at http://localhost:8000
# If issues found, go back to Step 1
```

---

## 💡 Why This Workflow?

**Workspace** (`C:\Users\dryan\WorkSpaces\KBM2.0`):
- Your main development environment
- Where Git commits are tracked
- Clean, predictable state

**Cloned Repo** (`C:\Users\dryan\KBM2.0`):
- Isolated Docker testing environment
- Can rebuild/destroy without affecting workspace
- Mirrors production deployment process

This separation ensures:
- ✅ No accidental commits from wrong directory
- ✅ Clean git history
- ✅ Easy to reset if Docker messes things up
- ✅ Can test deployment without breaking development

---

## 🆘 Troubleshooting

### "I made changes in the wrong directory"

```bash
# If you edited files in C:\Users\dryan\KBM2.0 by mistake:

# Option 1: Copy to workspace
cp /c/Users/dryan/KBM2.0/changed_file.py /c/Users/dryan/WorkSpaces/KBM2.0/

# Option 2: Use git diff to see changes, manually apply to workspace
cd /c/Users/dryan/KBM2.0
git diff changed_file.py
# Copy the changes manually to workspace version

# Then reset the cloned repo:
git reset --hard origin/main
```

### "Both directories are out of sync"

```bash
# Workspace is the source of truth
cd C:\Users\dryan\WorkSpaces\KBM2.0
git status  # Check what's changed

# If workspace has uncommitted changes, commit them:
git add .
git commit -m "Sync changes"
git push origin main

# Reset cloned repo to match GitHub:
cd /c/Users/dryan/KBM2.0
git reset --hard origin/main
```

### "Docker has old code after git pull"

```bash
# Always rebuild Docker after pulling new code:
cd /c/Users/dryan/KBM2.0
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

---

**Remember**:
- 💻 **Code in WORKSPACE**
- 🐳 **Test in CLONED REPO**
- 📤 **Push from WORKSPACE**
- 📥 **Pull to CLONED REPO**

**Last Updated**: 2025-10-20
