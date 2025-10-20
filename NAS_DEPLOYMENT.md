# Deploying KBM 2.0 to Ugreen NAS

## Complete Production Deployment Guide

This guide will walk you through deploying KBM 2.0 to your Ugreen NAS server for production use.

---

## Prerequisites Check

**Before starting, verify you're SSH'd into the NAS:**
```bash
# You should see your NAS hostname/IP in the prompt
whoami
hostname
pwd
```

---

## Step 1: Check System Information

Run these commands to understand your NAS environment:

```bash
# Check OS
cat /etc/os-release

# Check available disk space (need at least 10GB free)
df -h

# Check if Docker is installed
docker --version
docker-compose --version

# Check if Git is installed
git --version
```

**Expected outputs:**
- OS: Likely Ubuntu/Debian-based
- Docker: Version 20.10+ (if installed)
- Git: Any recent version

---

## Step 2: Install Docker (If Not Installed)

If Docker is not installed, install it:

```bash
# Update package list
sudo apt update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Log out and back in for group changes to take effect
exit
# SSH back in
```

---

## Step 3: Clone the Repository

Choose a location for your application (recommend `/opt` or `/home/yourusername`):

```bash
# Navigate to installation directory
cd /opt
# Or use: cd ~

# Clone the repository
sudo git clone https://github.com/DevinRyan-Vesta/KBM2.0.git
# Or without sudo if in home directory: git clone https://github.com/DevinRyan-Vesta/KBM2.0.git

# Navigate into the project
cd KBM2.0

# Check you have the latest code
git log -1 --oneline
```

**Expected**: You should see your latest commit about "Add workflow reminder..."

---

## Step 4: Configure Production Environment

Create and configure your production environment file:

```bash
# Navigate to project directory
cd /opt/KBM2.0
# Or: cd ~/KBM2.0

# Generate a secure SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"
# SAVE THIS OUTPUT - you'll need it in the next step!

# Create production environment file
cat > .env << 'EOF'
ENV=production
SECRET_KEY=REPLACE_WITH_YOUR_SECRET_KEY_FROM_ABOVE
AUTO_CREATE_SCHEMA=false
PORT=8000

# Session Security
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
PERMANENT_SESSION_LIFETIME=3600

# Rate Limiting
RATELIMIT_ENABLED=true
RATELIMIT_STORAGE_URL=memory://

# File Upload Limits
MAX_CONTENT_LENGTH=16777216

# Application Settings
FLASK_ENV=production
PYTHONUNBUFFERED=1
EOF

# Edit the file to add your SECRET_KEY
nano .env
# Replace REPLACE_WITH_YOUR_SECRET_KEY_FROM_ABOVE with the actual key
# Press Ctrl+X, then Y, then Enter to save
```

**Security Note**: The SECRET_KEY must be kept secret and never committed to Git!

---

## Step 5: Verify Docker Files

Check that all required files exist:

```bash
# Should see all these files:
ls -la Dockerfile compose.yaml entrypoint.sh .dockerignore .gitattributes

# Verify entrypoint.sh has Unix line endings (critical!)
file entrypoint.sh
# Should say: "Bourne-Again shell script, Unicode text, UTF-8 text executable"
# Should NOT say: "with CRLF line terminators"

# If it says CRLF, fix it:
sed -i 's/\r$//' entrypoint.sh
chmod +x entrypoint.sh
```

---

## Step 6: Build the Docker Image

Build the application Docker image:

```bash
# Make sure you're in the project directory
cd /opt/KBM2.0
# Or: cd ~/KBM2.0

# Build the Docker image (this will take 2-5 minutes)
docker-compose build --no-cache

# Expected output: Successful build with "Successfully tagged kbm20-python-app:latest"
```

**Troubleshooting**:
- If you get "permission denied": Run with `sudo docker-compose build --no-cache`
- If build fails: Check the error message and verify all files are present

---

## Step 7: Start the Application

Start the application containers:

```bash
# Start in detached mode (runs in background)
docker-compose up -d

# Check container status
docker-compose ps

# View logs
docker-compose logs -f
# Press Ctrl+C to exit logs (container keeps running)
```

**Expected**: Container should be "Up" and logs should show:
```
Starting KBM 2.0 Application
========================================
✓ Master database schema verified
Starting Gunicorn server...
Listening at: http://0.0.0.0:8000
```

---

## Step 8: Test Application Access

Test if the application is running:

```bash
# Test health endpoint
curl http://localhost:8000/health

# Expected output:
# {"multi_tenant":true,"ok":true}
```

**If successful**, the application is running! ✅

---

## Step 9: Create App Admin Account

Create your first App Admin account:

```bash
# Run the admin creation script
docker-compose exec python-app python create_app_admin.py

# Follow the prompts:
# - Enter your name (e.g., "Devin Ryan")
# - Enter your email (e.g., "devin@vestasells.com")
# - Enter a secure 4-digit PIN (NOT 1234!)
# - Confirm your PIN
```

**Save your credentials** - you'll need them to log in!

---

## Step 10: Configure Firewall

Open the necessary ports:

```bash
# Check if firewall is active
sudo ufw status

# If active, allow port 8000 (temporarily for testing)
sudo ufw allow 8000/tcp

# For production, you'll want:
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 22/tcp    # SSH (if not already allowed)
```

---

## Step 11: Test External Access

From your Windows machine, test accessing the application:

**Find your NAS IP address** (on the NAS):
```bash
hostname -I
# Example output: 192.168.1.100
```

**From your Windows machine** (open browser):
- Navigate to: `http://YOUR_NAS_IP:8000`
- Example: `http://192.168.1.100:8000`

You should see the KBM 2.0 landing page!

---

## Step 12: Set Up Reverse Proxy (Nginx) - OPTIONAL

For production, set up Nginx as a reverse proxy:

```bash
# Install Nginx
sudo apt install -y nginx

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/kbm

# Add this configuration:
```

```nginx
server {
    listen 80;
    server_name your-domain.com *.your-domain.com;

    # Or for IP-based access:
    # server_name YOUR_NAS_IP;

    client_max_body_size 16M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    location /static/ {
        alias /opt/KBM2.0/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
```

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/kbm /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# If successful, reload Nginx
sudo systemctl reload nginx

# Enable Nginx to start on boot
sudo systemctl enable nginx
```

**After Nginx setup**, access via:
- `http://your-domain.com` (if you have a domain)
- `http://YOUR_NAS_IP` (if using IP)

---

## Step 13: Set Up SSL (HTTPS) - OPTIONAL

For secure HTTPS access:

```bash
# Install Certbot
sudo apt install -y certbot python3-certbot-nginx

# Obtain SSL certificate (for domain-based setup)
sudo certbot --nginx -d your-domain.com -d *.your-domain.com

# Follow the prompts
# Certbot will automatically configure Nginx for HTTPS
```

**After SSL setup**, access via:
- `https://your-domain.com`

---

## Step 14: Set Up Automatic Backups

Create a backup script:

```bash
# Create backup directory
sudo mkdir -p /opt/kbm-backups

# Create backup script
sudo nano /opt/backup-kbm.sh
```

Add this content:

```bash
#!/bin/bash
BACKUP_DIR="/opt/kbm-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup database
cd /opt/KBM2.0
cp -r KBM2_data "$BACKUP_DIR/backup_$TIMESTAMP"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -type d -name "backup_*" -mtime +7 -exec rm -rf {} \;

echo "Backup completed: $TIMESTAMP"
```

```bash
# Make it executable
sudo chmod +x /opt/backup-kbm.sh

# Test the backup
sudo /opt/backup-kbm.sh

# Schedule daily backups (2 AM)
sudo crontab -e
# Add this line:
0 2 * * * /opt/backup-kbm.sh >> /var/log/kbm-backup.log 2>&1
```

---

## Step 15: Enable Auto-Start on Reboot

Ensure the application starts automatically:

```bash
# Create systemd service (if not using Docker's restart policy)
# Docker compose already has "restart: unless-stopped" in compose.yaml

# Test auto-start by rebooting
sudo reboot

# After reboot, SSH back in and check:
docker-compose -f /opt/KBM2.0/compose.yaml ps

# Should show container as "Up"
```

---

## Deployment Complete! ✅

Your KBM 2.0 application is now deployed and running on your NAS!

### Access Points

- **Application**: `http://YOUR_NAS_IP:8000` (or your domain if configured)
- **Admin Panel**: `http://YOUR_NAS_IP:8000/app-admin`
- **Health Check**: `http://YOUR_NAS_IP:8000/health`

### Quick Commands Reference

```bash
# View logs
docker-compose -f /opt/KBM2.0/compose.yaml logs -f

# Restart application
docker-compose -f /opt/KBM2.0/compose.yaml restart

# Stop application
docker-compose -f /opt/KBM2.0/compose.yaml down

# Start application
docker-compose -f /opt/KBM2.0/compose.yaml up -d

# Update application (after pushing changes to GitHub)
cd /opt/KBM2.0
git pull origin main
docker-compose build --no-cache
docker-compose down
docker-compose up -d
```

---

## Troubleshooting

### Container won't start

```bash
# Check logs
docker-compose logs

# Check if port 8000 is already in use
sudo netstat -tulpn | grep 8000

# Rebuild from scratch
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

### Can't access from other devices

```bash
# Check firewall
sudo ufw status

# Check if container is listening
docker-compose ps

# Check Nginx is running (if using)
sudo systemctl status nginx

# Check application is accessible locally
curl http://localhost:8000/health
```

### Database issues

```bash
# Check database files exist
ls -la /opt/KBM2.0/KBM2_data/

# Reset database (WARNING: Deletes all data!)
docker-compose down
rm -rf KBM2_data/*
docker-compose up -d
```

---

## Next Steps

1. ✅ Create your App Admin account
2. ✅ Access `/app-admin` and create first tenant account
3. ✅ Set up your first users
4. ✅ Configure domain name (optional)
5. ✅ Set up SSL certificate (optional)
6. ✅ Configure automated backups
7. ✅ Share access with your team!

---

## Security Checklist

- [ ] Changed default SECRET_KEY in `.env`
- [ ] Created strong PIN for App Admin (not 1234)
- [ ] Firewall configured (ports 80, 443, 22 only)
- [ ] SSL certificate installed (HTTPS)
- [ ] Automated backups configured
- [ ] `.env` file permissions secured: `chmod 600 .env`
- [ ] Regular updates scheduled

---

**Deployment Date**: 2025-10-20
**Version**: 1.0
**Server**: Ugreen NAS
