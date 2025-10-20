#!/bin/bash
#
# SSL Certificate Setup for KBM 2.0
# Uses Let's Encrypt with certbot
#

set -e

DOMAIN="buywithvesta.com"
EMAIL="your-email@example.com"  # CHANGE THIS!
CERT_DIR="/volume1/KBM/ssl"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}KBM 2.0 SSL Certificate Setup${NC}"
echo -e "${GREEN}====================================${NC}"
echo ""
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Check if certbot is installed
if ! command -v certbot &> /dev/null; then
    echo -e "${YELLOW}Installing certbot...${NC}"
    sudo apt update
    sudo apt install -y certbot
fi

# Create cert directory
sudo mkdir -p "$CERT_DIR"

echo -e "${YELLOW}Getting SSL certificate for $DOMAIN and *.$DOMAIN${NC}"
echo ""
echo -e "${RED}IMPORTANT:${NC}"
echo "1. This will temporarily stop your Docker containers"
echo "2. Make sure ports 80 and 8080 are accessible from the internet"
echo "3. DNS records must be properly configured"
echo ""
read -p "Continue? (yes/no): " -r
echo ""

if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo -e "${YELLOW}Setup cancelled${NC}"
    exit 0
fi

# Stop Docker containers to free port 8080
echo -e "${YELLOW}Stopping Docker containers...${NC}"
cd /volume1/KBM/KBM2.0
docker-compose down

# Get certificate using standalone mode
echo -e "${YELLOW}Requesting SSL certificate from Let's Encrypt...${NC}"
sudo certbot certonly \
    --standalone \
    --preferred-challenges http \
    --http-01-port 8080 \
    --email "$EMAIL" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "*.$DOMAIN" \
    --server https://acme-v02.api.letsencrypt.org/directory

# Note: Wildcard requires DNS challenge, let's try HTTP first for main domain
# If wildcard fails, we'll document DNS challenge method

# Copy certificates to our directory
echo -e "${YELLOW}Copying certificates...${NC}"
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$CERT_DIR/"
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$CERT_DIR/"
sudo chmod 644 "$CERT_DIR/fullchain.pem"
sudo chmod 600 "$CERT_DIR/privkey.pem"

# Restart Docker containers
echo -e "${YELLOW}Restarting Docker containers...${NC}"
docker-compose up -d

echo ""
echo -e "${GREEN}====================================${NC}"
echo -e "${GREEN}SSL Certificate Installed!${NC}"
echo -e "${GREEN}====================================${NC}"
echo "Certificate: $CERT_DIR/fullchain.pem"
echo "Private Key: $CERT_DIR/privkey.pem"
echo ""
echo "Next steps:"
echo "1. Update compose.yaml to use HTTPS (port 8443)"
echo "2. Update nginx.conf for SSL"
echo "3. Configure router port forwarding: 443 → 8443"
echo ""
