# HTTPS Setup Guide for KBM 2.0

This guide will help you enable HTTPS for your KBM 2.0 application using Let's Encrypt SSL certificates.

---

## Prerequisites

Before starting, ensure you have:

✅ Domain name pointing to your public IP (e.g., buywithvesta.com)
✅ Wildcard DNS record: `*.buywithvesta.com` → your public IP
✅ Router port forwarding:
   - External Port 80 → NAS IP:8080
   - External Port 443 → NAS IP:8443 (you'll add this)

---

## Quick Setup (Automated Script)

### Step 1: Update Docker Configuration

The Docker configuration has already been updated to support HTTPS:
- Port 8443 is mapped for HTTPS traffic
- nginx-ssl.conf is configured with SSL support
- SSL certificate volume is mounted

Just pull the latest code:

```bash
ssh your-nas-ip
cd /volume1/KBM/KBM2.0
git pull origin main
```

### Step 2: Run SSL Setup Script

```bash
cd /volume1/KBM/KBM2.0
chmod +x setup_ssl.sh
sudo bash setup_ssl.sh
```

The script will:
1. Install certbot if needed
2. Ask you to choose certificate type:
   - **Wildcard (recommended)**: Covers `*.buywithvesta.com` - requires DNS validation
   - **Main domain only**: Covers `buywithvesta.com` - uses HTTP validation
3. Guide you through the certificate acquisition process
4. Copy certificates to the correct location
5. Restart Docker containers with HTTPS enabled

### Step 3: Configure Router Port Forwarding

Add port forwarding rule in your router:

```
External Port: 443
Internal IP: <your NAS IP>
Internal Port: 8443
Protocol: TCP
```

### Step 4: Test HTTPS

From your phone or external network, visit:
- https://buywithvesta.com
- https://yourcompany.buywithvesta.com

You should see a secure connection with a valid certificate!

---

## Certificate Types Explained

### Option 1: Wildcard Certificate (Recommended)

**Covers**: `buywithvesta.com` AND `*.buywithvesta.com`
**Method**: DNS Challenge (manual)
**Difficulty**: Medium (requires DNS record update)

**Steps:**
1. Select option 1 in `setup_ssl.sh`
2. Certbot will display a TXT record to add
3. Log into your DNS provider (Namecheap, Cloudflare, etc.)
4. Add DNS TXT record: `_acme-challenge.buywithvesta.com`
5. Wait 2-5 minutes for propagation
6. Verify: `dig _acme-challenge.buywithvesta.com TXT`
7. Press Enter in certbot

**Why choose this?**
- Works for all subdomains (current and future tenants)
- You only need one certificate for everything

### Option 2: Main Domain Only

**Covers**: `buywithvesta.com` only
**Method**: HTTP Challenge (automatic)
**Difficulty**: Easy (fully automated)

**Steps:**
1. Select option 2 in `setup_ssl.sh`
2. Script automatically validates and installs

**Why choose this?**
- Simpler setup (no DNS changes needed)
- Good for testing or if you don't need subdomains

⚠️ **Note**: This won't work for tenant subdomains like `yourcompany.buywithvesta.com`

---

## Manual Certificate Acquisition

If the automated script doesn't work, you can get certificates manually:

### For Wildcard Certificate:

```bash
# Stop Docker containers
cd /volume1/KBM/KBM2.0
sudo docker compose down

# Get certificate
sudo certbot certonly \
  --manual \
  --preferred-challenges dns \
  --email your-email@example.com \
  --agree-tos \
  -d buywithvesta.com \
  -d *.buywithvesta.com

# Copy certificates
sudo mkdir -p /volume1/KBM/ssl
sudo cp /etc/letsencrypt/live/buywithvesta.com/fullchain.pem /volume1/KBM/ssl/
sudo cp /etc/letsencrypt/live/buywithvesta.com/privkey.pem /volume1/KBM/ssl/
sudo chmod 644 /volume1/KBM/ssl/fullchain.pem
sudo chmod 600 /volume1/KBM/ssl/privkey.pem

# Restart Docker
sudo docker compose up -d
```

### For Main Domain Only:

```bash
# Stop Docker containers
cd /volume1/KBM/KBM2.0
sudo docker compose down

# Get certificate
sudo certbot certonly \
  --standalone \
  --http-01-port 8080 \
  --email your-email@example.com \
  --agree-tos \
  -d buywithvesta.com

# Copy certificates
sudo mkdir -p /volume1/KBM/ssl
sudo cp /etc/letsencrypt/live/buywithvesta.com/fullchain.pem /volume1/KBM/ssl/
sudo cp /etc/letsencrypt/live/buywithvesta.com/privkey.pem /volume1/KBM/ssl/
sudo chmod 644 /volume1/KBM/ssl/fullchain.pem
sudo chmod 600 /volume1/KBM/ssl/privkey.pem

# Restart Docker
sudo docker compose up -d
```

---

## Automatic Certificate Renewal

SSL certificates expire every 90 days. Set up automatic renewal:

### Step 1: Make Renewal Script Executable

```bash
cd /volume1/KBM/KBM2.0
chmod +x renew_ssl.sh
```

### Step 2: Test Renewal

```bash
sudo bash renew_ssl.sh
```

### Step 3: Set Up Cron Job

```bash
sudo crontab -e
```

Add this line to run every Monday at 3 AM:

```
0 3 * * 1 /volume1/KBM/KBM2.0/renew_ssl.sh >> /volume1/KBM/ssl/renewal.log 2>&1
```

The script will:
- Check if certificate expires in < 30 days
- Skip renewal if still valid for > 30 days
- Automatically renew when needed
- Log all activity to `/volume1/KBM/ssl/renewal.log`

---

## Troubleshooting

### Certificate Request Fails

**Error**: "Connection refused" or "Port 80 not accessible"

**Solution**:
```bash
# Verify port forwarding
# Check from external network: curl http://buywithvesta.com

# Verify Docker is stopped during certbot
docker ps
```

**Error**: "DNS problem: NXDOMAIN"

**Solution**:
```bash
# Verify DNS is working
nslookup buywithvesta.com
dig buywithvesta.com

# Wait 5-10 minutes after DNS changes
```

### HTTPS Not Working

**Error**: "Connection refused" on port 443

**Solution**:
```bash
# Verify port forwarding: 443 → 8443
# Check nginx is listening
docker exec nginx-proxy netstat -tlnp | grep 443

# Check certificates exist
ls -la /volume1/KBM/ssl/
```

**Error**: "Certificate not trusted" or "SSL error"

**Solution**:
```bash
# Verify certificate is valid
openssl x509 -in /volume1/KBM/ssl/fullchain.pem -text -noout

# Check nginx config
docker exec nginx-proxy nginx -t

# Restart nginx
docker compose restart nginx
```

### Mixed Content Warnings

**Error**: Browser shows "Not Secure" even with HTTPS

**Solution**:
- All assets should use relative URLs (no hardcoded http://)
- Check browser console for mixed content warnings
- Update any http:// links to https:// or use protocol-relative URLs

---

## Reverting to HTTP Only

If you need to disable HTTPS:

```bash
cd /volume1/KBM/KBM2.0
git stash  # Save local changes
git checkout HEAD~1 compose.yaml  # Revert compose.yaml
docker compose down
docker compose up -d
```

Or manually edit `compose.yaml`:
- Remove port 8443 mapping
- Change nginx-ssl.conf back to nginx.conf
- Remove SSL volume mount

---

## Security Best Practices

✅ **Keep Certificates Updated**
- Set up automatic renewal (see above)
- Monitor `/volume1/KBM/ssl/renewal.log`

✅ **Strong SSL Configuration**
- TLS 1.2 and 1.3 only (already configured)
- Strong cipher suites (already configured)
- HSTS header enabled (already configured)

✅ **Protect Private Keys**
- Private key permissions: 600 (only root)
- Never commit keys to git
- Keep encrypted backups

✅ **Monitor Certificate Expiry**
```bash
# Check expiry date
openssl x509 -in /volume1/KBM/ssl/fullchain.pem -noout -enddate

# List all certificates
sudo certbot certificates
```

---

## Quick Commands Reference

```bash
# Get new certificate (automated)
sudo bash /volume1/KBM/KBM2.0/setup_ssl.sh

# Check certificate expiry
sudo certbot certificates

# Manually renew certificate
sudo bash /volume1/KBM/KBM2.0/renew_ssl.sh

# Test renewal (dry run)
sudo certbot renew --dry-run

# View certificate details
openssl x509 -in /volume1/KBM/ssl/fullchain.pem -text -noout

# Check nginx SSL config
docker exec nginx-proxy nginx -t

# Reload nginx
docker compose restart nginx

# View renewal logs
tail -f /volume1/KBM/ssl/renewal.log
```

---

## After HTTPS Is Working

Once you've verified HTTPS is working:

1. ✅ Test all subdomains
2. ✅ Verify certificate shows as trusted in browser
3. ✅ Set up automatic renewal cron job
4. ✅ Update any documentation with https:// URLs
5. ✅ Consider forcing HTTPS (nginx-ssl.conf already redirects HTTP to HTTPS)

---

## Need Help?

- Check logs: `docker compose logs nginx`
- Verify DNS: `dig buywithvesta.com`
- Test ports: `curl -v http://buywithvesta.com`
- Certificate info: `sudo certbot certificates`
