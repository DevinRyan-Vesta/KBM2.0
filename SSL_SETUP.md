# SSL/HTTPS Setup Guide for KBM 2.0

This guide will help you set up HTTPS with Let's Encrypt SSL certificates for your KBM 2.0 deployment.

---

## Prerequisites

✅ Domain pointing to your public IP (buywithvesta.com)
✅ Wildcard DNS record (*.buywithvesta.com → your IP)
✅ Router port forwarding configured:
   - Port 80 → NAS 8080 (HTTP)
   - Port 443 → NAS 8443 (HTTPS - to be configured)

---

## Method 1: Automated Setup (Recommended for Single Domain)

### Step 1: Update Email in Script

```bash
# On your NAS
cd /volume1/KBM/KBM2.0

# Edit the script
nano get_ssl_cert.sh

# Change this line:
EMAIL="your-email@example.com"  # Replace with YOUR actual email

# Save: Ctrl+X, Y, Enter
```

### Step 2: Make Script Executable

```bash
chmod +x get_ssl_cert.sh
sed -i 's/\r$//' get_ssl_cert.sh  # Fix line endings
```

### Step 3: Run the Script

```bash
# This will:
# 1. Install certbot
# 2. Stop Docker temporarily
# 3. Get SSL certificate
# 4. Restart Docker

sudo bash get_ssl_cert.sh
```

### Step 4: Enable SSL in Docker Compose

Edit `compose.yaml`:

```bash
nano compose.yaml
```

Update the nginx section:

```yaml
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    restart: unless-stopped
    ports:
      - "8080:80"    # HTTP
      - "8443:443"   # HTTPS
    volumes:
      - ./nginx-ssl.conf:/etc/nginx/conf.d/default.conf:ro
      - /volume1/KBM/ssl:/etc/nginx/ssl:ro  # SSL certificates
    depends_on:
      - python-app
    networks:
      - appnet
```

Save and restart:

```bash
docker-compose down
docker-compose up -d
```

### Step 5: Configure Router

Add port forwarding rule:
```
External Port: 443
Internal IP: <your NAS IP>
Internal Port: 8443
Protocol: TCP
```

### Step 6: Test HTTPS

From your phone or external network:
```
https://buywithvesta.com
https://yourcompany.buywithvesta.com
```

---

## Method 2: Manual Setup with DNS Challenge (For Wildcard Certificates)

Wildcard certificates (*.buywithvesta.com) require DNS validation.

### Step 1: Install Certbot

```bash
sudo apt update
sudo apt install -y certbot
```

### Step 2: Get Wildcard Certificate

```bash
# This will prompt you to add a TXT record to your DNS
sudo certbot certonly \
  --manual \
  --preferred-challenges dns \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d buywithvesta.com \
  -d *.buywithvesta.com
```

**Follow the prompts:**
1. Certbot will give you a TXT record to add to your DNS
2. Add the record: `_acme-challenge.buywithvesta.com` TXT `<value-from-certbot>`
3. Wait 2-5 minutes for DNS propagation
4. Verify with: `dig _acme-challenge.buywithvesta.com TXT`
5. Press Enter in certbot to continue

### Step 3: Copy Certificates

```bash
sudo mkdir -p /volume1/KBM/ssl
sudo cp /etc/letsencrypt/live/buywithvesta.com/fullchain.pem /volume1/KBM/ssl/
sudo cp /etc/letsencrypt/live/buywithvesta.com/privkey.pem /volume1/KBM/ssl/
sudo chmod 644 /volume1/KBM/ssl/fullchain.pem
sudo chmod 600 /volume1/KBM/ssl/privkey.pem
```

### Step 4: Update Docker Compose

Follow Step 4 from Method 1 above.

---

## Certificate Auto-Renewal

SSL certificates expire every 90 days. Set up automatic renewal:

### Create Renewal Script

```bash
nano /volume1/KBM/renew_ssl.sh
```

```bash
#!/bin/bash
# Renew SSL certificate

# Stop nginx to free port
cd /volume1/KBM/KBM2.0
docker-compose stop nginx

# Renew certificate
sudo certbot renew --quiet --standalone --http-01-port 8080

# Copy renewed certificates
sudo cp /etc/letsencrypt/live/buywithvesta.com/fullchain.pem /volume1/KBM/ssl/
sudo cp /etc/letsencrypt/live/buywithvesta.com/privkey.pem /volume1/KBM/ssl/
sudo chmod 644 /volume1/KBM/ssl/fullchain.pem
sudo chmod 600 /volume1/KBM/ssl/privkey.pem

# Restart nginx
docker-compose start nginx
```

Make it executable:

```bash
chmod +x /volume1/KBM/renew_ssl.sh
sed -i 's/\r$//' /volume1/KBM/renew_ssl.sh
```

### Set Up Cron Job

```bash
crontab -e
```

Add this line (runs every Monday at 3 AM):

```
0 3 * * 1 /volume1/KBM/renew_ssl.sh >> /volume1/KBM/ssl/renewal.log 2>&1
```

---

## Troubleshooting

### Certificate Request Fails

**Error: "Connection refused" or "Port 80 not accessible"**

**Solution:**
- Verify router port forwarding: 80 → NAS 8080
- Check firewall allows incoming port 80
- Test from outside: `curl http://buywithvesta.com/.well-known/test`

**Error: "DNS problem: NXDOMAIN"**

**Solution:**
- Verify DNS is propagated: `nslookup buywithvesta.com`
- Wait 5-10 minutes after DNS changes
- Check both @ and wildcard records

### HTTPS Not Working

**Error: "Connection refused" on port 443**

**Solution:**
- Verify router port forwarding: 443 → NAS 8443
- Check nginx is listening on 443: `docker exec nginx-proxy netstat -tlnp | grep 443`
- Check certificate files exist: `ls -la /volume1/KBM/ssl/`

**Error: "Certificate not trusted"**

**Solution:**
- Make sure you used production Let's Encrypt server (not staging)
- Verify certificate paths in `nginx-ssl.conf`
- Check certificate: `openssl x509 -in /volume1/KBM/ssl/fullchain.pem -text -noout`

### Mixed Content Warnings

**Error: Browser shows "Not Secure" with HTTPS**

**Solution:**
- Update BASE_DOMAIN in .env to use https:
  ```
  BASE_DOMAIN=buywithvesta.com
  ```
- Ensure all asset URLs use relative paths (not hardcoded http://)

---

## Security Best Practices

✅ **Use Strong SSL Configuration**
- TLS 1.2 and 1.3 only (configured in `nginx-ssl.conf`)
- Strong cipher suites
- HSTS header enabled

✅ **Keep Certificates Up to Date**
- Set up auto-renewal cron job
- Monitor renewal logs
- Test renewal: `sudo certbot renew --dry-run`

✅ **Protect Private Keys**
- Private key permissions: 600 (only root can read)
- Never commit private keys to git
- Keep backups encrypted

✅ **Monitor Certificate Expiry**
- Certificates expire in 90 days
- Let's Encrypt sends email warnings to registered email
- Check expiry: `sudo certbot certificates`

---

## Quick Reference

```bash
# Get new certificate
sudo bash get_ssl_cert.sh

# Check certificate expiry
sudo certbot certificates

# Renew certificates manually
sudo bash /volume1/KBM/renew_ssl.sh

# Test renewal (dry run)
sudo certbot renew --dry-run

# View certificate details
openssl x509 -in /volume1/KBM/ssl/fullchain.pem -text -noout

# Check nginx SSL config
docker exec nginx-proxy nginx -t

# Reload nginx after config changes
docker-compose restart nginx

# View renewal logs
tail -f /volume1/KBM/ssl/renewal.log
```

---

## After SSL Is Working

Once HTTPS is configured:

1. **Update .env** - Set SESSION_COOKIE_SECURE=true (already set)
2. **Test All Subdomains** - Verify wildcards work
3. **Update Documentation** - Note HTTPS URLs for users
4. **Monitor Logs** - Check for SSL errors

**Access URLs:**
- Root: `https://buywithvesta.com`
- App Admin: `https://buywithvesta.com/app-admin/login`
- Company: `https://[subdomain].buywithvesta.com`
