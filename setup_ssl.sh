#!/bin/bash
#
# SSL/HTTPS Setup Script for KBM 2.0
# This script helps you obtain and install SSL certificates
#

set -e

DOMAIN="buywithvesta.com"
EMAIL="devinryan.sc@gmail.com"  # Update this if needed
SSL_DIR="/volume1/KBM/ssl"
PROJECT_DIR="/volume1/KBM/KBM2.0"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}==========================================${NC}"
echo -e "${GREEN}   KBM 2.0 SSL/HTTPS Setup Script${NC}"
echo -e "${GREEN}==========================================${NC}"
echo ""
echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo "SSL Directory: $SSL_DIR"
echo ""

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root (use sudo)${NC}"
   exit 1
fi

# Function to check if certbot is installed
check_certbot() {
    if ! command -v certbot &> /dev/null; then
        echo -e "${YELLOW}Certbot not found. Installing...${NC}"
        apt update
        apt install -y certbot
        echo -e "${GREEN}Certbot installed successfully${NC}"
    else
        echo -e "${GREEN}Certbot is already installed${NC}"
    fi
}

# Function to create SSL directory
create_ssl_dir() {
    echo -e "${YELLOW}Creating SSL directory...${NC}"
    mkdir -p "$SSL_DIR"
    chmod 755 "$SSL_DIR"
    echo -e "${GREEN}SSL directory created: $SSL_DIR${NC}"
}

# Function to get certificate (main domain + wildcard using DNS challenge)
get_wildcard_cert() {
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}   Getting Wildcard SSL Certificate${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
    echo -e "${YELLOW}To get a wildcard certificate (*.buywithvesta.com), you must use DNS validation.${NC}"
    echo ""
    echo -e "${YELLOW}When prompted by certbot:${NC}"
    echo "1. Certbot will give you a TXT record value (long random string)"
    echo "2. Log into your DNS provider (e.g., Namecheap, Cloudflare, GoDaddy)"
    echo "3. Add a TXT record:"
    echo "   - Host/Name: ${BLUE}_acme-challenge${NC} (just this, NOT the full domain)"
    echo "   - Type: TXT"
    echo "   - Value: (paste the value certbot gives you)"
    echo "4. Wait 2-5 minutes for DNS propagation"
    echo "5. Verify with: dig _acme-challenge.$DOMAIN TXT"
    echo "   (You should see your TXT value in the response)"
    echo "6. Press Enter in certbot to continue"
    echo ""
    read -p "Press Enter to continue..."
    echo ""

    # Stop Docker containers to avoid conflicts
    echo -e "${YELLOW}Stopping Docker containers...${NC}"
    cd "$PROJECT_DIR"
    docker compose down

    # Get wildcard certificate using DNS challenge
    certbot certonly \
        --manual \
        --preferred-challenges dns \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN" \
        -d "*.$DOMAIN"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Certificate obtained successfully!${NC}"
    else
        echo -e "${RED}Failed to obtain certificate. Please check the errors above.${NC}"
        exit 1
    fi
}

# Function to get certificate (main domain only using HTTP challenge)
get_http_cert() {
    echo ""
    echo -e "${BLUE}==========================================${NC}"
    echo -e "${BLUE}   Getting SSL Certificate (HTTP)${NC}"
    echo -e "${BLUE}==========================================${NC}"
    echo ""
    echo -e "${YELLOW}This will get a certificate for $DOMAIN only (no wildcard).${NC}"
    echo -e "${YELLOW}Make sure port 80 is forwarded to your NAS port 8080.${NC}"
    echo ""
    read -p "Press Enter to continue..."
    echo ""

    # Stop Docker containers to free port 8080
    echo -e "${YELLOW}Stopping Docker containers...${NC}"
    cd "$PROJECT_DIR"
    docker compose down

    # Get certificate using HTTP challenge
    certbot certonly \
        --standalone \
        --http-01-port 8080 \
        --email "$EMAIL" \
        --agree-tos \
        --no-eff-email \
        -d "$DOMAIN"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Certificate obtained successfully!${NC}"
    else
        echo -e "${RED}Failed to obtain certificate. Please check the errors above.${NC}"
        exit 1
    fi
}

# Function to copy certificates
copy_certificates() {
    echo ""
    echo -e "${YELLOW}Copying certificates to $SSL_DIR...${NC}"

    if [ ! -d "/etc/letsencrypt/live/$DOMAIN" ]; then
        echo -e "${RED}Certificate directory not found!${NC}"
        exit 1
    fi

    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem "$SSL_DIR/"
    cp /etc/letsencrypt/live/$DOMAIN/privkey.pem "$SSL_DIR/"
    chmod 644 "$SSL_DIR/fullchain.pem"
    chmod 600 "$SSL_DIR/privkey.pem"

    echo -e "${GREEN}Certificates copied successfully${NC}"
    echo "  - Certificate: $SSL_DIR/fullchain.pem"
    echo "  - Private Key: $SSL_DIR/privkey.pem"
}

# Function to restart Docker
restart_docker() {
    echo ""
    echo -e "${YELLOW}Starting Docker containers...${NC}"
    cd "$PROJECT_DIR"
    docker compose up -d

    echo -e "${GREEN}Docker containers started${NC}"
}

# Function to verify certificate
verify_cert() {
    echo ""
    echo -e "${BLUE}Certificate Details:${NC}"
    openssl x509 -in "$SSL_DIR/fullchain.pem" -noout -subject -dates
    echo ""
}

# Function to show next steps
show_next_steps() {
    echo ""
    echo -e "${GREEN}==========================================${NC}"
    echo -e "${GREEN}   SSL Setup Complete!${NC}"
    echo -e "${GREEN}==========================================${NC}"
    echo ""
    echo -e "${YELLOW}Next Steps:${NC}"
    echo "1. Update your router port forwarding:"
    echo "   - External Port 80 → NAS IP:8080"
    echo "   - External Port 443 → NAS IP:8443"
    echo ""
    echo "2. Test HTTPS access:"
    echo "   - https://buywithvesta.com"
    echo "   - https://yourcompany.buywithvesta.com"
    echo ""
    echo "3. Set up automatic renewal:"
    echo "   - Edit /volume1/KBM/renew_ssl.sh"
    echo "   - Add to crontab: 0 3 * * 1 /volume1/KBM/renew_ssl.sh"
    echo ""
    echo -e "${YELLOW}Certificate expires in 90 days${NC}"
    echo ""
}

# Main menu
main() {
    check_certbot
    create_ssl_dir

    echo ""
    echo -e "${BLUE}Choose certificate type:${NC}"
    echo "1) Wildcard Certificate (*.buywithvesta.com) - Requires DNS validation"
    echo "2) Main Domain Only (buywithvesta.com) - HTTP validation"
    echo "3) Skip certificate (already have certificates)"
    echo ""
    read -p "Enter choice [1-3]: " choice

    case $choice in
        1)
            get_wildcard_cert
            copy_certificates
            restart_docker
            verify_cert
            show_next_steps
            ;;
        2)
            get_http_cert
            copy_certificates
            restart_docker
            verify_cert
            show_next_steps
            ;;
        3)
            echo -e "${YELLOW}Skipping certificate acquisition${NC}"

            if [ ! -f "$SSL_DIR/fullchain.pem" ] || [ ! -f "$SSL_DIR/privkey.pem" ]; then
                echo -e "${RED}Warning: Certificate files not found in $SSL_DIR${NC}"
                echo "Make sure to copy your certificates there before starting Docker"
            else
                echo -e "${GREEN}Certificate files found${NC}"
                verify_cert
            fi

            restart_docker
            show_next_steps
            ;;
        *)
            echo -e "${RED}Invalid choice${NC}"
            exit 1
            ;;
    esac
}

# Run main function
main
