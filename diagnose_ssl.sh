#!/bin/bash
#
# SSL/HTTPS Diagnostic Script for KBM 2.0
# Run this to diagnose connection issues
#

PROJECT_DIR="/volume1/KBM/KBM2.0"
SSL_DIR="/volume1/KBM/ssl"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}   KBM 2.0 HTTPS Diagnostics${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# Check 1: Docker containers
echo -e "${YELLOW}[1/6] Checking Docker containers...${NC}"
cd "$PROJECT_DIR"
containers=$(docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Ports}}")
if [ $? -eq 0 ]; then
    echo "$containers"

    # Check if containers are running
    if docker compose ps | grep -q "Up"; then
        echo -e "${GREEN}✓ Containers are running${NC}"
    else
        echo -e "${RED}✗ Containers are NOT running${NC}"
        echo -e "${YELLOW}  Fix: docker compose up -d${NC}"
    fi
else
    echo -e "${RED}✗ Could not check containers${NC}"
fi
echo ""

# Check 2: SSL certificates
echo -e "${YELLOW}[2/6] Checking SSL certificates...${NC}"
if [ -f "$SSL_DIR/fullchain.pem" ]; then
    echo -e "${GREEN}✓ Certificate found: $SSL_DIR/fullchain.pem${NC}"

    # Check expiry
    expiry=$(openssl x509 -in "$SSL_DIR/fullchain.pem" -noout -enddate 2>/dev/null)
    if [ $? -eq 0 ]; then
        echo "  $expiry"

        # Check if expired
        if openssl x509 -in "$SSL_DIR/fullchain.pem" -noout -checkend 0 2>/dev/null; then
            echo -e "${GREEN}  ✓ Certificate is valid${NC}"
        else
            echo -e "${RED}  ✗ Certificate is EXPIRED${NC}"
        fi
    fi
else
    echo -e "${RED}✗ Certificate NOT found: $SSL_DIR/fullchain.pem${NC}"
    echo -e "${YELLOW}  Fix: Run setup_ssl.sh to obtain certificate${NC}"
fi

if [ -f "$SSL_DIR/privkey.pem" ]; then
    echo -e "${GREEN}✓ Private key found: $SSL_DIR/privkey.pem${NC}"
else
    echo -e "${RED}✗ Private key NOT found: $SSL_DIR/privkey.pem${NC}"
fi
echo ""

# Check 3: Nginx configuration
echo -e "${YELLOW}[3/6] Checking nginx configuration...${NC}"
if docker exec nginx-proxy nginx -t 2>&1; then
    echo -e "${GREEN}✓ Nginx configuration is valid${NC}"
else
    echo -e "${RED}✗ Nginx configuration has errors${NC}"
    echo -e "${YELLOW}  Check the error above${NC}"
fi
echo ""

# Check 4: Port listening
echo -e "${YELLOW}[4/6] Checking port bindings...${NC}"
if docker exec nginx-proxy netstat -tlnp 2>/dev/null | grep -q ":80"; then
    echo -e "${GREEN}✓ Nginx listening on port 80${NC}"
else
    echo -e "${RED}✗ Nginx NOT listening on port 80${NC}"
fi

if docker exec nginx-proxy netstat -tlnp 2>/dev/null | grep -q ":443"; then
    echo -e "${GREEN}✓ Nginx listening on port 443${NC}"
else
    echo -e "${RED}✗ Nginx NOT listening on port 443${NC}"
fi
echo ""

# Check 5: Check nginx config file in use
echo -e "${YELLOW}[5/6] Checking nginx config file...${NC}"
config_in_container=$(docker exec nginx-proxy ls -la /etc/nginx/conf.d/default.conf 2>/dev/null)
if echo "$config_in_container" | grep -q "nginx-ssl.conf"; then
    echo -e "${GREEN}✓ Using SSL config (nginx-ssl.conf)${NC}"
elif echo "$config_in_container" | grep -q "nginx.conf"; then
    echo -e "${YELLOW}⚠ Using non-SSL config (nginx.conf)${NC}"
    echo -e "${YELLOW}  This might be why HTTPS isn't working${NC}"
else
    echo -e "${RED}✗ Could not determine config file${NC}"
fi
echo "$config_in_container"
echo ""

# Check 6: Container logs
echo -e "${YELLOW}[6/6] Recent nginx logs (last 20 lines)...${NC}"
docker logs nginx-proxy --tail 20 2>&1
echo ""

# Summary and recommendations
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}   Recommendations${NC}"
echo -e "${BLUE}==========================================${NC}"
echo ""

# Check if we can determine the issue
containers_running=$(docker compose ps | grep -c "Up" || echo "0")
cert_exists=$([ -f "$SSL_DIR/fullchain.pem" ] && echo "yes" || echo "no")
nginx_valid=$(docker exec nginx-proxy nginx -t 2>&1 | grep -q "syntax is ok" && echo "yes" || echo "no")

if [ "$containers_running" -eq 0 ]; then
    echo -e "${RED}ISSUE: Docker containers are not running${NC}"
    echo -e "${YELLOW}Solution:${NC}"
    echo "  cd $PROJECT_DIR"
    echo "  docker compose up -d"
    echo ""
elif [ "$cert_exists" == "no" ]; then
    echo -e "${RED}ISSUE: SSL certificates are missing${NC}"
    echo -e "${YELLOW}Solution:${NC}"
    echo "  cd $PROJECT_DIR"
    echo "  sudo bash setup_ssl.sh"
    echo ""
elif [ "$nginx_valid" == "no" ]; then
    echo -e "${RED}ISSUE: Nginx configuration has errors${NC}"
    echo -e "${YELLOW}Solution:${NC}"
    echo "  Check the nginx error above and fix the configuration"
    echo "  You may need to revert to HTTP-only mode temporarily"
    echo ""
else
    echo -e "${YELLOW}Containers appear to be running. Additional checks:${NC}"
    echo ""
    echo "1. Test local access:"
    echo "   curl -k https://localhost:8443"
    echo ""
    echo "2. Check if you can reach the NAS from outside:"
    echo "   (From your phone on cellular) https://buywithvesta.com"
    echo ""
    echo "3. Verify router port forwarding:"
    echo "   - Port 80 → NAS IP:8080"
    echo "   - Port 443 → NAS IP:8443"
    echo ""
    echo "4. Check firewall rules on NAS"
    echo ""
fi

echo -e "${BLUE}==========================================${NC}"
