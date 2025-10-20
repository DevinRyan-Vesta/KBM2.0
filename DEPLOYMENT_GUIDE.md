# KBM 2.0 - Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Preparation](#pre-deployment-preparation)
3. [Deployment Methods](#deployment-methods)
4. [Method 1: Docker Deployment (Recommended)](#method-1-docker-deployment-recommended)
5. [Method 2: Traditional Server Deployment](#method-2-traditional-server-deployment)
6. [Method 3: Cloud Platform Deployment](#method-3-cloud-platform-deployment)
7. [Post-Deployment Configuration](#post-deployment-configuration)
8. [Initial Setup](#initial-setup)
9. [Troubleshooting](#troubleshooting)
10. [Maintenance](#maintenance)

---

## Prerequisites

### Server Requirements

**Minimum Requirements (Small Deployment, < 10 users)**:
- **CPU**: 2 cores
- **RAM**: 2 GB
- **Disk**: 20 GB SSD
- **OS**: Ubuntu 20.04+ LTS, Debian 11+, CentOS 8+, or RHEL 8+

**Recommended Requirements (Medium Deployment, 10-50 users)**:
- **CPU**: 4 cores
- **RAM**: 4 GB
- **Disk**: 50 GB SSD
- **OS**: Ubuntu 22.04 LTS (recommended)

**Large Deployment (50+ users)**:
- **CPU**: 8+ cores
- **RAM**: 8+ GB
- **Disk**: 100+ GB SSD
- **Database**: Separate PostgreSQL/MySQL server
- **Load Balancer**: Multiple application servers behind load balancer

### Software Requirements

- **Python**: 3.11 or higher
- **Docker**: 20.10+ (for Docker deployment)
- **Docker Compose**: 2.0+ (for Docker deployment)
- **Git**: For cloning repository
- **Web Server**: Nginx or Apache (for reverse proxy)
- **Database**: SQLite (included) or PostgreSQL/MySQL for production

### Domain Requirements

- **Domain Name**: Your domain (e.g., example.com)
- **Wildcard DNS**: Configure *.example.com to point to your server
- **SSL Certificate**: Wildcard SSL certificate (*.example.com, example.com)

### Knowledge Requirements

Basic understanding of:
- Linux command line
- SSH access
- Basic networking (DNS, ports, firewalls)
- Text editor (nano, vim, or equivalent)

---

## Pre-Deployment Preparation

### Step 1: Clone the Repository

```bash
# SSH into your server
ssh user@your-server-ip

# Navigate to your desired location
cd /opt

# Clone the repository
git clone https://github.com/yourusername/KBM2.0.git
cd KBM2.0
```

### Step 2: Generate Secret Keys

```bash
# Generate a secure SECRET_KEY
python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))"

# Save the output - you'll need it for environment configuration
```

### Step 3: Configure DNS

**Add Wildcard DNS Record**:

In your domain registrar or DNS provider:
```
Type: A
Host: *
Value: YOUR_SERVER_IP
TTL: 3600 (or auto)

Type: A
Host: @
Value: YOUR_SERVER_IP
TTL: 3600 (or auto)
```

**Verify DNS propagation**:
```bash
# Check root domain
dig yourdomain.com +short

# Check wildcard (replace tenant with any subdomain)
dig tenant.yourdomain.com +short
```

Both should return your server's IP address.

### Step 4: Obtain SSL Certificate

**Option A: Let's Encrypt (Free, Recommended)**

```bash
# Install Certbot
sudo apt update
sudo apt install -y certbot python3-certbot-nginx

# Obtain wildcard certificate (requires DNS challenge)
sudo certbot certonly --manual --preferred-challenges dns \
  -d yourdomain.com -d *.yourdomain.com

# Follow the prompts to add DNS TXT records
```

**Option B: Commercial Certificate**

Purchase a wildcard SSL certificate from your provider and upload to server.

---

## Deployment Methods

Choose one of the following deployment methods based on your needs:

- **Method 1 (Recommended)**: Docker Deployment - Easiest, most portable
- **Method 2**: Traditional Server - More control, requires more setup
- **Method 3**: Cloud Platform - AWS, GCP, Azure specific instructions

---

## Method 1: Docker Deployment (Recommended)

### Step 1: Install Docker and Docker Compose

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add your user to docker group (optional, for non-root access)
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Log out and back in for group changes to take effect
```

### Step 2: Verify Project Files

The repository includes all necessary Docker files. Verify they exist:

```bash
# Verify required files are present
ls -la Dockerfile compose.yaml entrypoint.sh .dockerignore .gitattributes

# Expected output should show all these files
# The .gitattributes file ensures shell scripts maintain Unix line endings (LF)
# even when working on Windows
```

**Note**: The `entrypoint.sh` file is included in the repository and should have Unix (LF) line endings. If you're on Windows and encounter "No such file or directory" errors, the `.gitattributes` file will automatically ensure correct line endings.

### Step 3: Configure Environment Variables

```bash
# Create production environment file
cat > .env << 'EOF'
ENV=production
SECRET_KEY=REPLACE_WITH_YOUR_SECRET_KEY_FROM_STEP_2
AUTO_CREATE_SCHEMA=false
PORT=8000

# Database Configuration (if using PostgreSQL/MySQL)
# DATABASE_URI=postgresql://username:password@localhost:5432/kbm_master

# Application Settings
FLASK_ENV=production
PYTHONUNBUFFERED=1
EOF

# Secure the file
chmod 600 .env

# IMPORTANT: Edit the file and replace REPLACE_WITH_YOUR_SECRET_KEY_FROM_STEP_2
nano .env
```

### Step 4: Configure Docker Compose (Optional)

**Note**: The repository includes a working `compose.yaml` file. You only need to modify it if you want to customize ports, volumes, or other settings.

```bash
# Optional: Customize compose.yaml if needed
cat > compose.yaml << 'EOF'
services:
  kbm-app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: kbm-app
    restart: unless-stopped
    init: true
    ports:
      - "127.0.0.1:8000:8000"  # Only expose to localhost, nginx will proxy
    env_file:
      - .env
    volumes:
      - kbm-data:/app/KBM2_data  # Persist database files
      - kbm-logs:/app/logs        # Persist logs
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

volumes:
  kbm-data:
    driver: local
  kbm-logs:
    driver: local
EOF
```

### Step 5: Build and Start the Application

```bash
# Build the Docker image
docker-compose build

# Start the application in detached mode
docker-compose up -d

# Check logs
docker-compose logs -f

# Verify the container is running
docker-compose ps

# Test the application
curl http://localhost:8000/health
# Should return: {"ok":true,"multi_tenant":true}
```

### Step 6: Configure Nginx Reverse Proxy

```bash
# Install Nginx
sudo apt install -y nginx

# Create Nginx configuration
sudo nano /etc/nginx/sites-available/kbm

# Add the following configuration:
```

```nginx
# KBM 2.0 Nginx Configuration

# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name yourdomain.com *.yourdomain.com;

    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }

    location / {
        return 301 https://$host$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name yourdomain.com *.yourdomain.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logging
    access_log /var/log/nginx/kbm_access.log;
    error_log /var/log/nginx/kbm_error.log;

    # Client body size limit (for file uploads)
    client_max_body_size 16M;

    # Static files
    location /static/ {
        alias /opt/KBM2.0/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy to application
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
}
```

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/kbm /etc/nginx/sites-enabled/

# Test Nginx configuration
sudo nginx -t

# Reload Nginx
sudo systemctl reload nginx

# Enable Nginx to start on boot
sudo systemctl enable nginx
```

### Step 7: Configure Firewall

```bash
# If using UFW (Ubuntu)
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw enable

# If using firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Step 8: Test the Deployment

```bash
# Test root domain
curl -I https://yourdomain.com/health

# Test subdomain
curl -I https://test.yourdomain.com/

# Expected: Redirect or response from application
```

### Step 9: Set Up SSL Auto-Renewal

```bash
# Test renewal (dry run)
sudo certbot renew --dry-run

# Certbot automatically sets up a cron job or systemd timer
# Verify it's configured:
sudo systemctl list-timers | grep certbot
```

**Docker Deployment Complete!** Proceed to [Post-Deployment Configuration](#post-deployment-configuration).

---

### Alternative: Using Docker Desktop UI

If you prefer using a graphical interface instead of the command line, Docker Desktop provides an intuitive UI for managing containers, images, and volumes.

#### Prerequisites

1. **Download and Install Docker Desktop**:
   - **Windows**: Download from [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop)
   - **Mac**: Download from [Docker Desktop for Mac](https://www.docker.com/products/docker-desktop)
   - **Linux**: Use Docker Engine with [Docker Desktop for Linux](https://docs.docker.com/desktop/install/linux-install/)

2. **Start Docker Desktop**:
   - Launch the Docker Desktop application
   - Wait for the Docker engine to start (the whale icon should show "Docker Desktop is running")

#### Step 1: Prepare Project Files

Before using Docker Desktop, ensure you've completed the preparation steps from the CLI deployment:

1. Clone the repository
2. Create [`.env`](#step-3-configure-environment-variables) file with your configuration
3. Ensure [`entrypoint.sh`](#step-2-create-missing-entrypointsh-file) exists and is executable
4. Verify `compose.yaml` and `Dockerfile` are present

```bash
# In your terminal (one-time setup)
cd /path/to/KBM2.0

# Create .env file with your settings
nano .env

# Verify required files exist
ls -la compose.yaml Dockerfile entrypoint.sh .env
```

#### Step 2: Open Project in Docker Desktop

**Method A: Using the UI**

1. Open Docker Desktop
2. Click **"Images"** in the left sidebar
3. At the top right, click **"Build"** button (or look for import options)
4. Navigate to your `KBM2.0` folder
5. Docker Desktop will detect the `compose.yaml` file

**Method B: Using Terminal (Recommended)**

Even with Docker Desktop, it's easiest to do the initial build from terminal:

```bash
cd /path/to/KBM2.0
docker-compose build
```

Then manage everything else through the UI!

#### Step 3: Build the Image via Docker Desktop UI

If you prefer building through the UI:

1. **Open Docker Desktop**
2. Click **"Images"** in the left sidebar
3. Click **"Build"** or use the search bar to find build options
4. **Build via CLI is recommended** (simpler for compose projects):
   ```bash
   docker-compose build
   ```
5. Once built, the image will appear in Docker Desktop under **Images** tab:
   - Look for: `kbm20-kbm-app` or similar name

#### Step 4: Start Containers via UI

1. **Navigate to Images**:
   - Click **"Images"** in the left sidebar
   - Find your `kbm20-kbm-app` image

2. **Run the Container**:
   - Hover over the image and click **"Run"**
   - **Or** use the compose file:
     - In terminal: `docker-compose up -d`
     - The containers will now appear in Docker Desktop

3. **Using Docker Compose in UI** (Recommended):
   - After running `docker-compose up -d` in terminal
   - Open Docker Desktop → Click **"Containers"** in left sidebar
   - You'll see a container group named `kbm20` (or your folder name)
   - Click the dropdown arrow to expand and see individual containers

#### Step 5: Configure Container Settings (Optional)

If running manually (not recommended for compose projects):

1. When clicking **"Run"** on an image, a dialog appears:

   **Container name**: `kbm-app`

   **Ports**:
   - Host Port: `8000`
   - Container Port: `8000`

   **Volumes**:
   - Click **"+"** to add volumes
   - Host Path: Choose a folder for data persistence (e.g., `C:\kbm-data`)
   - Container Path: `/app/KBM2_data`

   **Environment Variables**:
   - Click **"+"** to add each variable from your `.env` file:
     - `ENV` = `production`
     - `SECRET_KEY` = `your-secret-key`
     - `PORT` = `8000`
     - etc.

2. Click **"Run"** to start the container

**Note**: Using `docker-compose up -d` from terminal is much easier than manual configuration, as it reads all settings from `compose.yaml` and `.env` automatically.

#### Step 6: Manage Containers in Docker Desktop

**Viewing Containers**:

1. Click **"Containers"** in the left sidebar
2. You'll see all running containers
3. For compose projects, containers are grouped together

**Container Actions** (hover over container for icons):

- **▶️ Start**: Start a stopped container
- **⏸️ Stop**: Stop a running container
- **🔄 Restart**: Restart the container
- **🗑️ Delete**: Remove the container (data in volumes is preserved)

**Container Details** (click on container name):

- **Logs**: View real-time application logs
- **Inspect**: See detailed container information
- **Stats**: View CPU, memory, and network usage
- **Terminal**: Open a shell inside the container
- **Files**: Browse the container's filesystem

#### Step 7: View Logs in Docker Desktop

**Real-time Logs**:

1. Click **"Containers"** in the left sidebar
2. Click on your `kbm-app` container
3. The **Logs** tab opens automatically showing live output
4. **Search logs**: Use the search box at the top
5. **Copy logs**: Click the copy icon to copy all logs
6. **Clear logs**: Click the trash icon to clear the view (doesn't delete actual logs)

**Log Filtering**:

- Type in the search box to filter logs
- Example: Search for `ERROR` to see only errors

#### Step 8: Manage Volumes in Docker Desktop

**View Volumes**:

1. Click **"Volumes"** in the left sidebar
2. You'll see volumes like:
   - `kbm20_kbm-data` (database storage)
   - `kbm20_kbm-logs` (log files)

**Volume Actions**:

- **Inspect**: Click on a volume to see which containers use it
- **Delete**: Remove unused volumes (⚠️ This deletes data!)
- **Export**: Right-click → Export to backup volume data

**Browse Volume Data**:

1. Click on a volume (e.g., `kbm20_kbm-data`)
2. Click **"Data"** tab to browse files
3. You can view (but not easily edit) files through the UI

**Backup Volumes**:

Docker Desktop doesn't have built-in backup UI. Use terminal:

```bash
# Backup a volume
docker run --rm -v kbm20_kbm-data:/data -v $(pwd):/backup ubuntu tar czf /backup/kbm-data-backup.tar.gz /data

# Restore a volume
docker run --rm -v kbm20_kbm-data:/data -v $(pwd):/backup ubuntu tar xzf /backup/kbm-data-backup.tar.gz -C /
```

#### Step 9: Update Application via Docker Desktop

**When you need to update the application**:

1. **Pull latest code** (in terminal):
   ```bash
   cd /path/to/KBM2.0
   git pull
   ```

2. **Rebuild image** (choose one):

   **Option A - Terminal** (Recommended):
   ```bash
   docker-compose build
   ```

   **Option B - Docker Desktop UI**:
   - Click **"Images"**
   - Right-click on `kbm20-kbm-app` → **"Remove"**
   - Rebuild using `docker-compose build` in terminal

3. **Restart containers**:

   **Via UI**:
   - Click **"Containers"**
   - Click stop button on `kbm-app`
   - Click the play button to restart

   **Via Terminal**:
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **Verify update**:
   - Click **"Containers"** → `kbm-app` → **"Logs"**
   - Look for "Starting KBM 2.0 Application..." message

#### Step 10: Troubleshooting with Docker Desktop

**Container Won't Start**:

1. Click **"Containers"** → Click on the failed container
2. Go to **"Logs"** tab to see error messages
3. Common issues:
   - **Port already in use**: Change port in `compose.yaml` or stop conflicting service
   - **Missing .env file**: Ensure `.env` exists in project folder
   - **Permission errors**: Check volume mount paths

**View Container Resource Usage**:

1. Click **"Containers"**
2. Click on running container
3. Click **"Stats"** tab
4. View real-time:
   - CPU usage
   - Memory usage
   - Network I/O
   - Disk I/O

**Access Container Shell**:

1. Click **"Containers"** → Click your container
2. Click **"Terminal"** tab (or "Exec" tab)
3. You're now inside the container's bash shell
4. Useful commands:
   ```bash
   # Check if database exists
   ls -la /app/KBM2_data/

   # Check environment variables
   env | grep ENV

   # Test application manually
   python -c "from app_multitenant import create_app; print('OK')"
   ```

**Reset Everything** (Nuclear Option):

If things are completely broken:

1. **Stop all containers**:
   - Docker Desktop → **"Containers"** → Click stop on all KBM containers

2. **Remove containers**:
   - Click delete icon on each container

3. **Remove volumes** (⚠️ Deletes all data!):
   - Docker Desktop → **"Volumes"** → Delete `kbm20_kbm-data` and `kbm20_kbm-logs`

4. **Rebuild from scratch**:
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

#### Step 11: Production Checklist (Docker Desktop)

Before going live:

- [ ] **Environment file**: `.env` has production settings and secure SECRET_KEY
- [ ] **Container running**: Green status in Docker Desktop Containers tab
- [ ] **Logs are clean**: No errors in Logs tab
- [ ] **Health check passing**: Container shows healthy status
- [ ] **Volumes mounted**: `kbm-data` and `kbm-logs` volumes exist
- [ ] **Backup strategy**: Plan for backing up volumes (see Step 8)
- [ ] **Nginx configured**: Reverse proxy set up (see [Step 6](#step-6-configure-nginx-reverse-proxy))
- [ ] **SSL certificate**: HTTPS working with valid certificate

#### Docker Desktop UI vs CLI Quick Reference

| Task | Docker Desktop UI | Command Line |
|------|------------------|--------------|
| **Build Image** | Images → Build | `docker-compose build` |
| **Start Containers** | Containers → Click ▶️ | `docker-compose up -d` |
| **Stop Containers** | Containers → Click ⏸️ | `docker-compose down` |
| **View Logs** | Containers → Container → Logs tab | `docker-compose logs -f` |
| **Restart Container** | Containers → Click 🔄 | `docker-compose restart` |
| **Delete Container** | Containers → Click 🗑️ | `docker-compose down` |
| **View Stats** | Containers → Container → Stats | `docker stats` |
| **Shell Access** | Containers → Container → Terminal | `docker exec -it kbm-app bash` |
| **Manage Volumes** | Volumes → Select volume | `docker volume ls` |
| **Update App** | Stop → Rebuild → Start | `docker-compose down && docker-compose build && docker-compose up -d` |

#### Tips for Docker Desktop Users

1. **Use Terminal for Compose**: Even with Docker Desktop, running `docker-compose` commands in terminal is often simpler than manual UI configuration

2. **Monitor Resources**: Use the Stats tab to ensure your application isn't running out of memory

3. **Export Logs**: When troubleshooting, use the copy button to export logs and share with support

4. **Volume Backups**: Set up automated backups of the `kbm-data` volume for disaster recovery

5. **Container Names**: Docker Desktop automatically prefixes containers with the project folder name (e.g., `kbm20-kbm-app`)

6. **Docker Desktop Settings**:
   - **Resources**: Allocate sufficient CPU/RAM (Settings → Resources)
   - **File Sharing**: Ensure project folder is in shared directories (Settings → Resources → File Sharing)

**Docker Desktop UI Deployment Complete!** Proceed to [Post-Deployment Configuration](#post-deployment-configuration).

---

## Method 2: Traditional Server Deployment

### Step 1: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install -y software-properties-common
sudo add-apt-repository -y ppa:deadsnakes/ppa
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev

# Install other dependencies
sudo apt install -y \
    build-essential \
    git \
    nginx \
    supervisor \
    curl \
    libpq-dev

# Verify Python version
python3.11 --version
```

### Step 2: Create Application User

```bash
# Create dedicated user for the application
sudo useradd -m -s /bin/bash kbmapp
sudo usermod -aG www-data kbmapp

# Switch to application user
sudo su - kbmapp
```

### Step 3: Clone and Set Up Application

```bash
# Clone repository
cd /home/kbmapp
git clone https://github.com/yourusername/KBM2.0.git
cd KBM2.0

# Create virtual environment
python3.11 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Install Gunicorn
pip install gunicorn
```

### Step 4: Configure Environment

```bash
# Create .env file
cat > .env << 'EOF'
ENV=production
SECRET_KEY=REPLACE_WITH_YOUR_SECRET_KEY
AUTO_CREATE_SCHEMA=false
PORT=8000
FLASK_ENV=production
PYTHONUNBUFFERED=1
EOF

# Secure the file
chmod 600 .env

# Edit and add your secret key
nano .env
```

### Step 5: Initialize Database

```bash
# Activate virtual environment if not already active
source /home/kbmapp/KBM2.0/.venv/bin/activate

# Create data directory
mkdir -p /home/kbmapp/KBM2.0/KBM2_data

# Run setup script
python setup_multitenant.py

# Expected output: "Master database initialized successfully"
```

### Step 6: Test the Application

```bash
# Start application manually (for testing)
cd /home/kbmapp/KBM2.0
source .venv/bin/activate
gunicorn --bind 127.0.0.1:8000 --workers 2 app_multitenant:app

# In another terminal, test
curl http://localhost:8000/health

# Stop with Ctrl+C when test is successful
```

### Step 7: Configure Supervisor (Process Manager)

```bash
# Exit from kbmapp user back to your admin user
exit

# Create supervisor configuration
sudo nano /etc/supervisor/conf.d/kbm.conf
```

Add the following configuration:

```ini
[program:kbm]
command=/home/kbmapp/KBM2.0/.venv/bin/gunicorn --bind 127.0.0.1:8000 --workers 4 --timeout 120 --access-logfile /home/kbmapp/KBM2.0/logs/access.log --error-logfile /home/kbmapp/KBM2.0/logs/error.log app_multitenant:app
directory=/home/kbmapp/KBM2.0
user=kbmapp
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/supervisor/kbm.err.log
stdout_logfile=/var/log/supervisor/kbm.out.log
environment=PATH="/home/kbmapp/KBM2.0/.venv/bin"
```

```bash
# Create logs directory
sudo su - kbmapp -c "mkdir -p /home/kbmapp/KBM2.0/logs"

# Reload supervisor
sudo supervisorctl reread
sudo supervisorctl update

# Start the application
sudo supervisorctl start kbm

# Check status
sudo supervisorctl status kbm

# View logs
sudo supervisorctl tail -f kbm
```

### Step 8: Configure Nginx

Follow the same Nginx configuration from [Step 6 of Docker Deployment](#step-6-configure-nginx-reverse-proxy), but update the static files path:

```nginx
# Static files location for traditional deployment
location /static/ {
    alias /home/kbmapp/KBM2.0/static/;
    expires 30d;
    add_header Cache-Control "public, immutable";
}
```

### Step 9: Configure Firewall

Same as Docker deployment [Step 7](#step-7-configure-firewall).

### Step 10: Set Up Systemd Service (Alternative to Supervisor)

If you prefer systemd over supervisor:

```bash
sudo nano /etc/systemd/system/kbm.service
```

```ini
[Unit]
Description=KBM 2.0 Application
After=network.target

[Service]
Type=notify
User=kbmapp
Group=www-data
WorkingDirectory=/home/kbmapp/KBM2.0
Environment="PATH=/home/kbmapp/KBM2.0/.venv/bin"
ExecStart=/home/kbmapp/KBM2.0/.venv/bin/gunicorn \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile /home/kbmapp/KBM2.0/logs/access.log \
    --error-logfile /home/kbmapp/KBM2.0/logs/error.log \
    app_multitenant:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# Reload systemd
sudo systemctl daemon-reload

# Start service
sudo systemctl start kbm

# Enable on boot
sudo systemctl enable kbm

# Check status
sudo systemctl status kbm

# View logs
sudo journalctl -u kbm -f
```

**Traditional Deployment Complete!** Proceed to [Post-Deployment Configuration](#post-deployment-configuration).

---

## Method 3: Cloud Platform Deployment

### AWS Elastic Beanstalk

```bash
# Install EB CLI
pip install awsebcli

# Initialize Elastic Beanstalk
eb init -p python-3.11 kbm-app --region us-east-1

# Create environment
eb create kbm-production

# Deploy
eb deploy

# Set environment variables
eb setenv SECRET_KEY=your-secret-key ENV=production

# Open application
eb open
```

### Google Cloud Platform (App Engine)

Create `app.yaml`:

```yaml
runtime: python311
entrypoint: gunicorn -b :$PORT app_multitenant:app

instance_class: F2

automatic_scaling:
  target_cpu_utilization: 0.65
  min_instances: 1
  max_instances: 10

env_variables:
  ENV: "production"
  SECRET_KEY: "your-secret-key"
```

```bash
# Deploy
gcloud app deploy
```

### Azure App Service

```bash
# Create resource group
az group create --name kbm-rg --location eastus

# Create app service plan
az appservice plan create --name kbm-plan --resource-group kbm-rg --sku B1 --is-linux

# Create web app
az webapp create --resource-group kbm-rg --plan kbm-plan --name kbm-app --runtime "PYTHON|3.11"

# Deploy
az webapp up --name kbm-app

# Set environment variables
az webapp config appsettings set --name kbm-app --resource-group kbm-rg --settings \
  SECRET_KEY="your-secret-key" \
  ENV="production"
```

---

## Post-Deployment Configuration

### Step 1: Create App Admin User

```bash
# For Docker deployment
docker-compose exec kbm-app python create_admin.py

# For traditional deployment
cd /home/kbmapp/KBM2.0
source .venv/bin/activate
python create_admin.py
```

Follow the prompts to create an application administrator account.

### Step 2: Verify Health Check

```bash
curl https://yourdomain.com/health
```

Expected response:
```json
{"ok":true,"multi_tenant":true}
```

### Step 3: Configure Backup Schedule

#### For SQLite (Docker)

```bash
# Create backup script
cat > /opt/backup-kbm.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/kbm-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup master database
docker-compose exec -T kbm-app sqlite3 /app/KBM2_data/master.db ".backup /app/KBM2_data/master_backup_$TIMESTAMP.db"

# Copy backups from container
docker cp kbm-app:/app/KBM2_data/master_backup_$TIMESTAMP.db "$BACKUP_DIR/"

# Backup all tenant databases
for db in $(docker-compose exec -T kbm-app ls /app/KBM2_data/*.db); do
    docker cp kbm-app:$db "$BACKUP_DIR/"
done

# Keep only last 7 days of backups
find "$BACKUP_DIR" -type f -name "*.db" -mtime +7 -delete

echo "Backup completed: $TIMESTAMP"
EOF

chmod +x /opt/backup-kbm.sh

# Schedule with cron
crontab -e

# Add this line (runs daily at 2 AM):
0 2 * * * /opt/backup-kbm.sh >> /var/log/kbm-backup.log 2>&1
```

#### For PostgreSQL/MySQL

```bash
# PostgreSQL backup script
cat > /opt/backup-kbm-db.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/kbm-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_USER="your_db_user"
DB_NAME="kbm_master"

mkdir -p "$BACKUP_DIR"

# Backup master database
PGPASSWORD="your_password" pg_dump -U "$DB_USER" -h localhost "$DB_NAME" > "$BACKUP_DIR/master_$TIMESTAMP.sql"

# Compress backup
gzip "$BACKUP_DIR/master_$TIMESTAMP.sql"

# Keep only last 7 days
find "$BACKUP_DIR" -type f -name "*.sql.gz" -mtime +7 -delete

echo "Backup completed: $TIMESTAMP"
EOF

chmod +x /opt/backup-kbm-db.sh
```

### Step 4: Configure Log Rotation

```bash
# Create logrotate configuration
sudo nano /etc/logrotate.d/kbm
```

```
/home/kbmapp/KBM2.0/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 kbmapp www-data
    sharedscripts
    postrotate
        supervisorctl restart kbm > /dev/null 2>&1 || true
    endscript
}
```

### Step 5: Set Up Monitoring

#### Basic Monitoring Script

```bash
cat > /opt/monitor-kbm.sh << 'EOF'
#!/bin/bash

# Check if application is responding
if ! curl -f -s https://yourdomain.com/health > /dev/null; then
    echo "Application health check failed!" | mail -s "KBM Alert" admin@yourdomain.com

    # Restart application (Docker)
    docker-compose -f /opt/KBM2.0/compose.yaml restart

    # Or for traditional deployment:
    # sudo supervisorctl restart kbm
fi

# Check disk space
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 80 ]; then
    echo "Disk usage is above 80%: ${DISK_USAGE}%" | mail -s "KBM Disk Alert" admin@yourdomain.com
fi
EOF

chmod +x /opt/monitor-kbm.sh

# Schedule monitoring (every 5 minutes)
crontab -e
# Add:
*/5 * * * * /opt/monitor-kbm.sh
```

---

## Initial Setup

### Step 1: Access the Application

1. Open your browser and navigate to: `https://yourdomain.com`
2. You should see the landing page

### Step 2: Create First Tenant Account

1. Click "Sign Up" or navigate to `https://yourdomain.com/accounts/signup`
2. Fill in:
   - **Company Name**: Your company name
   - **Subdomain**: Choose a subdomain (e.g., "vesta" for vesta.yourdomain.com)
   - **Contact Email**: Your email address
3. Click "Create Account"

### Step 3: Create First User

1. After account creation, you'll be redirected to create the first user
2. Fill in:
   - **Name**: Your full name
   - **Email**: Your email
   - **PIN**: 4-digit PIN code
   - **Role**: Admin (default for first user)
3. Click "Create User"

### Step 4: Log In

1. Navigate to: `https://yoursubdomain.yourdomain.com`
2. Enter your email and PIN
3. Click "Login"

### Step 5: Configure Settings

1. Click your name in the top right
2. Go to "Settings" (if available) or start adding inventory

### Step 6: Add Initial Data

1. **Add Properties**: Navigate to Properties → Add New Property
2. **Add Keys**: Navigate to Inventory → Keys → Add Key
3. **Add Lockboxes**: Navigate to Inventory → Lockboxes → Add Lockbox
4. **Add Users**: Navigate to Users → Add User

---

## Troubleshooting

### Application Won't Start

#### Docker Deployment

```bash
# Check container logs
docker-compose logs -f

# Check container status
docker-compose ps

# Restart containers
docker-compose restart

# Rebuild if needed
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

#### Traditional Deployment

```bash
# Check supervisor status
sudo supervisorctl status kbm

# View logs
sudo supervisorctl tail -f kbm stderr

# Restart service
sudo supervisorctl restart kbm

# Check Python errors
cd /home/kbmapp/KBM2.0
source .venv/bin/activate
python app_multitenant.py
```

### Database Connection Errors

```bash
# Check database file permissions
ls -la KBM2_data/

# For Docker:
docker-compose exec kbm-app ls -la /app/KBM2_data/

# Verify database exists
sqlite3 KBM2_data/master.db ".tables"
```

### Nginx Issues

```bash
# Check Nginx status
sudo systemctl status nginx

# Test configuration
sudo nginx -t

# View error logs
sudo tail -f /var/log/nginx/kbm_error.log

# Restart Nginx
sudo systemctl restart nginx
```

### SSL Certificate Issues

```bash
# Check certificate validity
sudo certbot certificates

# Renew certificate
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run
```

### Subdomain Not Working

1. **Verify DNS**:
   ```bash
   dig yoursubdomain.yourdomain.com +short
   ```

2. **Check Nginx configuration**:
   ```bash
   sudo nginx -t
   grep -r "server_name" /etc/nginx/sites-enabled/
   ```

3. **Verify application**:
   ```bash
   curl -H "Host: yoursubdomain.yourdomain.com" http://localhost:8000/
   ```

### Application Slow or Unresponsive

1. **Check server resources**:
   ```bash
   top
   free -h
   df -h
   ```

2. **Check database size**:
   ```bash
   du -sh KBM2_data/*.db
   ```

3. **Restart application**:
   ```bash
   # Docker
   docker-compose restart

   # Traditional
   sudo supervisorctl restart kbm
   ```

4. **Increase Gunicorn workers**:
   - Edit `entrypoint.sh` or supervisor config
   - Increase `--workers` parameter
   - Restart application

### Cannot Create New Tenant

1. **Check logs**:
   ```bash
   docker-compose logs -f | grep ERROR
   ```

2. **Verify database permissions**:
   ```bash
   ls -la KBM2_data/
   ```

3. **Check subdomain availability**:
   ```bash
   # Connect to database
   sqlite3 KBM2_data/master.db "SELECT subdomain FROM accounts;"
   ```

---

## Maintenance

### Updating the Application

#### Docker Deployment

```bash
cd /opt/KBM2.0

# Pull latest code
git pull

# Rebuild image
docker-compose build

# Stop application
docker-compose down

# Start with new image
docker-compose up -d

# Check logs
docker-compose logs -f
```

#### Traditional Deployment

```bash
cd /home/kbmapp/KBM2.0

# Pull latest code
git pull

# Activate virtual environment
source .venv/bin/activate

# Update dependencies
pip install -r requirements.txt

# Restart application
sudo supervisorctl restart kbm

# Check status
sudo supervisorctl status kbm
```

### Database Maintenance

#### Vacuum SQLite Database (Optimize)

```bash
# For each database
sqlite3 KBM2_data/master.db "VACUUM;"
sqlite3 KBM2_data/tenant1.db "VACUUM;"
```

#### Check Database Integrity

```bash
sqlite3 KBM2_data/master.db "PRAGMA integrity_check;"
```

### Monitoring Disk Space

```bash
# Check disk usage
df -h

# Check KBM data directory
du -sh KBM2_data/

# Find large files
find KBM2_data/ -type f -size +100M -ls
```

### Viewing Logs

#### Docker

```bash
# Application logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Search logs
docker-compose logs | grep ERROR
```

#### Traditional

```bash
# Supervisor logs
sudo supervisorctl tail -f kbm

# Nginx access logs
sudo tail -f /var/log/nginx/kbm_access.log

# Nginx error logs
sudo tail -f /var/log/nginx/kbm_error.log

# Application logs
tail -f /home/kbmapp/KBM2.0/logs/error.log
```

### Security Updates

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Update Python packages
cd /home/kbmapp/KBM2.0
source .venv/bin/activate
pip list --outdated
pip install --upgrade package-name

# Restart application after updates
```

---

## Next Steps

After successful deployment:

1. Review [PRE_DEPLOYMENT_CHECKLIST.md](PRE_DEPLOYMENT_CHECKLIST.md) for security hardening
2. Set up regular backups
3. Configure monitoring and alerting
4. Train users on the system
5. Create user documentation
6. Plan for scaling (if needed)

---

## Support

For issues or questions:

1. Check logs first
2. Review this troubleshooting section
3. Check project documentation
4. Search GitHub issues
5. Create a new GitHub issue with:
   - Deployment method
   - Error messages
   - Relevant log excerpts
   - Steps to reproduce

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20
**Tested On**: Ubuntu 22.04 LTS, Docker 24.0.5
**Author**: Claude (Anthropic)
**Project**: KBM 2.0 Multi-Tenant Application
