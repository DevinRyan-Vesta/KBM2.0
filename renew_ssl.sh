#!/bin/bash
#
# SSL Certificate Renewal Script for KBM 2.0
# Run this script via cron to automatically renew certificates
# Recommended: 0 3 * * 1 /volume1/KBM/renew_ssl.sh >> /volume1/KBM/ssl/renewal.log 2>&1
#

set -e

DOMAIN="buywithvesta.com"
SSL_DIR="/volume1/KBM/ssl"
PROJECT_DIR="/volume1/KBM/KBM2.0"

echo "==================================="
echo "SSL Certificate Renewal"
echo "==================================="
echo "Date: $(date)"
echo "Domain: $DOMAIN"
echo ""

# Check if certificates are due for renewal
echo "Checking certificate expiry..."
if ! certbot certificates | grep -q "$DOMAIN"; then
    echo "ERROR: No certificates found for $DOMAIN"
    exit 1
fi

# Check days until expiry
days_until_expiry=$(openssl x509 -in "$SSL_DIR/fullchain.pem" -noout -enddate | cut -d= -f2 | xargs -I {} date -d {} +%s | awk -v now=$(date +%s) '{print int(($1-now)/86400)}')
echo "Certificate expires in $days_until_expiry days"

# Only renew if less than 30 days until expiry
if [ $days_until_expiry -gt 30 ]; then
    echo "Certificate is still valid for $days_until_expiry days. Skipping renewal."
    exit 0
fi

echo "Certificate needs renewal. Proceeding..."
echo ""

# Stop nginx to free port 80
echo "Stopping nginx container..."
cd "$PROJECT_DIR"
docker compose stop nginx

# Renew certificate
echo "Renewing certificate..."
certbot renew --quiet --standalone --http-01-port 8080

if [ $? -ne 0 ]; then
    echo "ERROR: Certificate renewal failed"
    # Restart nginx even if renewal failed
    docker compose start nginx
    exit 1
fi

echo "Certificate renewed successfully"

# Copy renewed certificates
echo "Copying renewed certificates..."
cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$SSL_DIR/"
cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$SSL_DIR/"
chmod 644 "$SSL_DIR/fullchain.pem"
chmod 600 "$SSL_DIR/privkey.pem"

# Restart nginx
echo "Restarting nginx container..."
docker compose start nginx

echo ""
echo "==================================="
echo "Renewal Complete!"
echo "==================================="
echo "New certificate expires: $(openssl x509 -in "$SSL_DIR/fullchain.pem" -noout -enddate | cut -d= -f2)"
echo ""
