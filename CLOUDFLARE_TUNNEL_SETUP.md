# Cloudflare Tunnel Setup Guide

This guide will help you set up Cloudflare Tunnel for KBM 2.0, which eliminates the need for port forwarding and provides better security and performance.

---

## Why Cloudflare Tunnel?

**Benefits over traditional port forwarding:**
- ✅ **No port forwarding needed** - Works even if ISP blocks ports
- ✅ **Hide your home IP** - Attackers can't find your real IP address
- ✅ **DDoS protection** - Cloudflare blocks attacks automatically
- ✅ **Global CDN** - Faster performance worldwide
- ✅ **Zero Trust** - Built-in access controls
- ✅ **100% FREE** - No credit card required

---

## Prerequisites

Before starting, you need:
1. **Cloudflare account** (free)
2. **Domain registered** (you have buywithvesta.com)
3. **SSH access to NAS**

---

## Step-by-Step Setup

### Step 1: Create Cloudflare Account (2 minutes)

1. Go to https://dash.cloudflare.com/sign-up
2. Enter email: `devinryan.sc@gmail.com`
3. Create a password
4. Verify your email

### Step 2: Add Domain to Cloudflare (2 minutes)

1. Log into Cloudflare dashboard
2. Click **"Add a site"**
3. Enter: `buywithvesta.com`
4. Click **"Add site"**
5. Select **"Free"** plan
6. Click **"Continue"**

Cloudflare will scan your existing DNS records and import them.

7. Review the imported records
8. Click **"Continue"**

### Step 3: Update Nameservers (2 minutes + wait time)

Cloudflare will show you two nameservers like:

```
chad.ns.cloudflare.com
lara.ns.cloudflare.com
```

**Update your nameservers at Namecheap:**

1. Log into Namecheap
2. Go to **Domain List** → **Manage** (for buywithvesta.com)
3. Find **"Nameservers"** section
4. Change from **"Namecheap BasicDNS"** to **"Custom DNS"**
5. Enter the two Cloudflare nameservers
6. Click **"Save"**

**Wait 5-30 minutes** for nameserver propagation. Cloudflare will email you when it's active.

You can check status in Cloudflare dashboard - it will show:
- ⏳ Pending (nameservers not updated yet)
- ✅ Active (nameservers updated successfully)

### Step 4: Install Cloudflare Tunnel (5 minutes)

Once Cloudflare shows "Active", run the setup script:

**SSH into your NAS:**
```bash
ssh your-nas-ip
cd /volume1/KBM/KBM2.0
chmod +x setup_cloudflare_tunnel.sh
sudo bash setup_cloudflare_tunnel.sh
```

**The script will:**
1. Install `cloudflared` tool
2. Open browser for Cloudflare authentication
3. Create a tunnel named `kbm-tunnel`
4. Configure DNS routing for buywithvesta.com and *.buywithvesta.com
5. Set up automatic startup

**During the script:**
- A browser window will open for authentication
- Log in to Cloudflare and authorize the tunnel
- The script will automatically configure everything else

### Step 5: Test the Connection (1 minute)

After the script completes, wait 1-2 minutes for the tunnel to establish.

**Test from any device:**
```
https://buywithvesta.com
```

You should see your KBM login page - served through Cloudflare!

**Test tenant subdomains:**
```
https://yourcompany.buywithvesta.com
```

---

## Verify Everything is Working

### Check Tunnel Status

```bash
sudo systemctl status cloudflared
```

You should see:
```
● cloudflared.service - Cloudflare Tunnel
   Active: active (running)
```

### View Tunnel Logs

```bash
sudo journalctl -u cloudflared -f
```

You should see:
```
Connection established
Registered tunnel connection
```

### List All Tunnels

```bash
cloudflared tunnel list
```

---

## What Changed?

### Before (Port Forwarding):
```
Internet → Your Router (port 443) → NAS (port 8443) → Docker → App
```

### After (Cloudflare Tunnel):
```
Internet → Cloudflare (global CDN) → Encrypted Tunnel → NAS → Docker → App
```

**Key differences:**
- No port forwarding needed
- Your home IP is hidden
- Traffic goes through Cloudflare's network
- Automatic DDoS protection
- SSL certificates managed by Cloudflare

---

## Remove Port Forwarding (Optional but Recommended)

Since you're now using Cloudflare Tunnel, you can **remove the port forwarding rules** from your Eero router:

1. Open Eero app
2. Go to port forwarding settings
3. Delete the rules for ports 80 and 443
4. Save changes

**Why remove them?**
- You don't need them anymore
- Reduces attack surface
- Simplifies your network

---

## Cloudflare Dashboard Overview

In the Cloudflare dashboard for buywithvesta.com:

### Traffic Tab
- See real-time traffic to your site
- View threats blocked
- Monitor bandwidth usage

### DNS Tab
- Manage DNS records
- You'll see CNAME records for the tunnel:
  - `buywithvesta.com` → `<tunnel-id>.cfargotunnel.com`
  - `*.buywithvesta.com` → `<tunnel-id>.cfargotunnel.com`

### Zero Trust Tab (optional advanced features)
- Access controls
- Application policies
- Identity providers

---

## Troubleshooting

### Issue: "This site can't be reached"

**Check tunnel status:**
```bash
sudo systemctl status cloudflared
```

**If not running:**
```bash
sudo systemctl start cloudflared
sudo journalctl -u cloudflared -f
```

### Issue: "Cloudflare is not active yet"

**Check nameserver propagation:**
```bash
dig NS buywithvesta.com
```

You should see Cloudflare nameservers in the response.

**Wait time:** Nameserver changes can take 5-30 minutes to propagate.

### Issue: Tunnel shows as down in Cloudflare dashboard

**Restart the tunnel:**
```bash
sudo systemctl restart cloudflared
```

**Check credentials:**
```bash
ls -la ~/.cloudflared/
```

You should see:
- `config.yml`
- `<tunnel-id>.json`

### Issue: "403 Forbidden" or "Bad Gateway"

**Check if Docker containers are running:**
```bash
docker compose ps
```

**Restart Docker if needed:**
```bash
cd /volume1/KBM/KBM2.0
docker compose restart
```

---

## Managing Your Tunnel

### Start/Stop/Restart Tunnel

```bash
sudo systemctl start cloudflared    # Start
sudo systemctl stop cloudflared     # Stop
sudo systemctl restart cloudflared  # Restart
sudo systemctl status cloudflared   # Check status
```

### View Live Logs

```bash
sudo journalctl -u cloudflared -f
```

### List All Tunnels

```bash
cloudflared tunnel list
```

### Get Tunnel Info

```bash
cloudflared tunnel info kbm-tunnel
```

### Delete a Tunnel

```bash
cloudflared tunnel delete kbm-tunnel
```

---

## Advanced Configuration

### Custom Tunnel Configuration

Edit: `~/.cloudflared/config.yml`

```yaml
tunnel: <tunnel-id>
credentials-file: /root/.cloudflared/<tunnel-id>.json

ingress:
  # Main domain
  - hostname: buywithvesta.com
    service: http://localhost:8080

  # Wildcard subdomains
  - hostname: "*.buywithvesta.com"
    service: http://localhost:8080

  # Catch-all (required)
  - service: http_status:404
```

After editing, restart the tunnel:
```bash
sudo systemctl restart cloudflared
```

### Access Controls (Optional)

You can add authentication requirements in Cloudflare dashboard:

1. Go to **Zero Trust** → **Access** → **Applications**
2. Click **"Add an application"**
3. Choose **"Self-hosted"**
4. Set up authentication rules (email, Google, etc.)

This adds an extra login layer before accessing your app.

---

## SSL Certificates

### Cloudflare Manages SSL Automatically

With Cloudflare Tunnel:
- ✅ SSL certificates are automatic
- ✅ Auto-renewal handled by Cloudflare
- ✅ No Let's Encrypt needed
- ✅ Works on standard port 443

### What About Your Local Certificates?

The Let's Encrypt certificates you set up earlier are no longer needed for external access (Cloudflare handles SSL).

However, they don't hurt anything. You can:
- **Keep them**: No harm, just unused for external traffic
- **Remove them**: Delete `/volume1/KBM/ssl/` if you want

---

## Performance

### How Fast is Cloudflare Tunnel?

**Typical latency:**
- Direct port forwarding: 20-50ms
- Through Cloudflare Tunnel: 25-60ms

**Additional 5-10ms** is negligible and worth the benefits:
- DDoS protection
- Hidden IP
- Global CDN
- No port forwarding hassles

### Monitor Performance

In Cloudflare dashboard:
- **Analytics** tab shows response times
- **Traffic** tab shows bandwidth usage

---

## Security Notes

### What Cloudflare Can See

Cloudflare acts as a reverse proxy, so they can see:
- ✅ Domain names
- ✅ URL paths
- ✅ Traffic metadata

They **cannot** see:
- ❌ Content (if using E2E encryption)
- ❌ Login credentials (HTTPS is still encrypted)
- ❌ Database data

### Your Data is Safe

- Traffic between Cloudflare and your NAS is encrypted
- Traffic between users and Cloudflare is HTTPS
- Cloudflare is trusted by millions of sites worldwide

---

## Cost

**Cloudflare Tunnel is completely FREE:**
- ✅ No bandwidth limits
- ✅ No traffic limits
- ✅ No connection limits
- ✅ No credit card required
- ✅ No hidden fees

**Optional paid features (not needed for KBM):**
- Advanced DDoS protection ($20/mo)
- Advanced access controls ($7/user/mo)
- WAF rules ($20/mo)

For KBM 2.0, the **free tier is perfect**.

---

## Backup Plan

If Cloudflare Tunnel ever stops working:
1. Re-enable port forwarding in Eero router (443 → 8443)
2. Stop cloudflared: `sudo systemctl stop cloudflared`
3. Access directly via your public IP

---

## Support Resources

- **Cloudflare Docs**: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/
- **Community Forum**: https://community.cloudflare.com/
- **Status Page**: https://www.cloudflarestatus.com/

---

## Summary

✅ **No port forwarding** - Works regardless of router or ISP
✅ **Better security** - IP hidden, DDoS protection
✅ **Faster** - Global CDN
✅ **Easier** - No router configuration
✅ **Free** - Forever

**You're all set!** 🎉
