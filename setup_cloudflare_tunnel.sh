#!/bin/bash
#
# Cloudflare Tunnel Setup Script for KBM 2.0
# This replaces port forwarding with a secure tunnel
#

set -e

DOMAIN="buywithvesta.com"
TUNNEL_NAME="kbm-tunnel"
PROJECT_DIR="/volume1/KBM/KBM2.0"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}   Cloudflare Tunnel Setup for KBM 2.0${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Step 1: Install cloudflared
echo -e "${YELLOW}[1/5] Installing cloudflared...${NC}"
if command -v cloudflared &> /dev/null; then
    echo -e "${GREEN}✓ cloudflared is already installed${NC}"
    cloudflared --version
else
    echo "Installing cloudflared..."

    # Download and install cloudflared for Linux AMD64
    wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared

    echo -e "${GREEN}✓ cloudflared installed${NC}"
    cloudflared --version
fi
echo ""

# Step 2: Login to Cloudflare
echo -e "${YELLOW}[2/5] Authenticate with Cloudflare...${NC}"
echo -e "${BLUE}A browser window will open. Please log in to Cloudflare and authorize the tunnel.${NC}"
echo ""
read -p "Press Enter to open the browser and authenticate..."

cloudflared tunnel login

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Successfully authenticated with Cloudflare${NC}"
else
    echo -e "${RED}✗ Authentication failed. Please try again.${NC}"
    exit 1
fi
echo ""

# Step 3: Create tunnel
echo -e "${YELLOW}[3/5] Creating Cloudflare Tunnel...${NC}"

# Check if tunnel already exists
if cloudflared tunnel list | grep -q "$TUNNEL_NAME"; then
    echo -e "${YELLOW}⚠ Tunnel '$TUNNEL_NAME' already exists${NC}"
    read -p "Delete and recreate? (yes/no): " -r
    if [[ $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        cloudflared tunnel delete -f "$TUNNEL_NAME"
        cloudflared tunnel create "$TUNNEL_NAME"
    fi
else
    cloudflared tunnel create "$TUNNEL_NAME"
fi

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Tunnel created${NC}"
else
    echo -e "${RED}✗ Failed to create tunnel${NC}"
    exit 1
fi

# Get tunnel ID
TUNNEL_ID=$(cloudflared tunnel list | grep "$TUNNEL_NAME" | awk '{print $1}')
echo "Tunnel ID: $TUNNEL_ID"
echo ""

# Step 4: Create tunnel configuration
echo -e "${YELLOW}[4/5] Creating tunnel configuration...${NC}"

mkdir -p ~/.cloudflared

cat > ~/.cloudflared/config.yml <<EOF
tunnel: $TUNNEL_ID
credentials-file: /root/.cloudflared/$TUNNEL_ID.json

ingress:
  # Route root domain and all subdomains to nginx
  - hostname: $DOMAIN
    service: http://localhost:8080
  - hostname: "*.$DOMAIN"
    service: http://localhost:8080
  # Catch-all rule (required)
  - service: http_status:404
EOF

echo -e "${GREEN}✓ Configuration created at ~/.cloudflared/config.yml${NC}"
echo ""

# Step 5: Configure DNS
echo -e "${YELLOW}[5/5] Configuring DNS routes...${NC}"
echo ""
echo -e "${BLUE}Creating DNS routes for:${NC}"
echo "  - $DOMAIN"
echo "  - *.$DOMAIN (wildcard)"
echo ""

# Route main domain
cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN"

# Route wildcard
cloudflared tunnel route dns "$TUNNEL_NAME" "*.$DOMAIN"

echo -e "${GREEN}✓ DNS routes configured${NC}"
echo ""

# Create systemd service for auto-start
echo -e "${YELLOW}Creating systemd service for auto-start...${NC}"

cat > /etc/systemd/system/cloudflared.service <<EOF
[Unit]
Description=Cloudflare Tunnel
After=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/cloudflared tunnel run $TUNNEL_NAME
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable cloudflared
systemctl start cloudflared

echo -e "${GREEN}✓ Systemd service created and started${NC}"
echo ""

# Summary
echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}   Setup Complete!${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. Wait 1-2 minutes for tunnel to establish"
echo "2. Visit: ${BLUE}https://$DOMAIN${NC}"
echo "3. Visit: ${BLUE}https://yourcompany.$DOMAIN${NC}"
echo ""
echo -e "${YELLOW}Check tunnel status:${NC}"
echo "  systemctl status cloudflared"
echo ""
echo -e "${YELLOW}View tunnel logs:${NC}"
echo "  journalctl -u cloudflared -f"
echo ""
echo -e "${YELLOW}Manage tunnels:${NC}"
echo "  cloudflared tunnel list"
echo "  cloudflared tunnel info $TUNNEL_NAME"
echo ""
echo -e "${GREEN}You can now remove port forwarding from your router!${NC}"
echo ""
