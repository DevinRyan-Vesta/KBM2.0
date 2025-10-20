# KBM 2.0 - Key & Lockbox Management System

![Status](https://img.shields.io/badge/status-production_ready-green) ![Security](https://img.shields.io/badge/security-hardened-brightgreen) ![Python](https://img.shields.io/badge/python-3.11+-blue)

**Multi-Tenant Property Management Solution**

Complete web application for managing keys, lockboxes, signs, and smart locks for property management businesses.

---

## 🚀 Quick Start

### Using Docker (Recommended)

```bash
# Build and start
docker-compose build
docker-compose up -d

# Check logs
docker-compose logs -f

# Visit http://localhost:8000
```

### Manual Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize database
python setup_multitenant.py

# Run application
python app_multitenant.py

# Visit http://localhost:5000
```

---

## 📚 Complete Documentation

**Essential Reading** (in this order):

1. **[PRE_DEPLOYMENT_CHECKLIST.md](PRE_DEPLOYMENT_CHECKLIST.md)** - Security overview and readiness checklist ⚠️ READ FIRST
2. **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)** - Complete step-by-step deployment instructions
3. **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** - Technical architecture and code documentation
4. **[USER_QUICKSTART_GUIDE.md](USER_QUICKSTART_GUIDE.md)** - End-user manual and feature guide
5. **[SECURITY_FIXES_APPLIED.md](SECURITY_FIXES_APPLIED.md)** - Security hardening summary

---

## ✅ Security Status

All critical security items have been addressed:

- ✅ Secure SECRET_KEY generated (64-char cryptographic key)
- ✅ Debug routes disabled for production
- ✅ CSRF protection enabled (Flask-WTF)
- ✅ Rate limiting configured (50 requests/hour)
- ✅ Secure session cookies (HttpOnly, Secure, SameSite)
- ✅ Comprehensive .gitignore (prevents credential leaks)
- ✅ Production environment files configured

See [SECURITY_FIXES_APPLIED.md](SECURITY_FIXES_APPLIED.md) for details.

---

## 🎯 Key Features

- 🔐 **Multi-Tenant** - Complete data isolation per customer
- 🗝️ **Inventory** - Keys, lockboxes, signs, smart locks
- 📦 **Checkout** - Track checkouts with PDF receipts
- 🏢 **Properties** - Manage properties, units, contacts
- 📊 **Reports** - Activity logs and analytics
- 📥 **Import/Export** - Bulk operations with Excel
- 🔒 **Secure** - CSRF, rate limiting, encrypted sessions

---

## 🏗️ Architecture

```
Browser → Nginx (HTTPS) → Flask App → SQLite Databases
                                     ├─ master.db (accounts)
                                     └─ {tenant}.db (inventory)
```

**Multi-Tenant Design**: Each customer gets isolated subdomain and database

- `vesta.example.com` → `vesta.db`
- `acme.example.com` → `acme.db`

---

## 🐳 Docker Deployment

### Requirements
- Docker 20.10+
- Docker Compose 2.0+
- Python 3.11+ (slim base image)

### Build and Run

```bash
docker-compose up --build
```

Application accessible at **http://localhost:8000**

### Configuration

Edit `.env.production` before deployment:

```bash
ENV=production
SECRET_KEY=<YOUR-SECURE-KEY-HERE>
RATELIMIT_ENABLED=true
SESSION_COOKIE_SECURE=true
```

Generate secure key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 📋 System Requirements

**Minimum** (Development/Small):
- CPU: 2 cores
- RAM: 2 GB
- Disk: 20 GB

**Recommended** (Production):
- CPU: 4+ cores
- RAM: 4+ GB
- Disk: 50+ GB SSD
- OS: Ubuntu 22.04 LTS

---

## 🔧 Technology Stack

- **Backend**: Flask 3.1.0
- **Database**: SQLite / PostgreSQL / MySQL
- **ORM**: SQLAlchemy 2.0.37
- **Auth**: Flask-Login 0.6.3
- **Security**: Flask-WTF, Flask-Limiter
- **Server**: Gunicorn 23.0.0
- **Docs**: ReportLab 4.2.5
- **Excel**: openpyxl 3.1.5

---

## 👥 User Roles

| Role | Access Level |
|------|-------------|
| **App Admin** | Platform administration |
| **Admin** | Full tenant access + user management |
| **Staff** | Inventory management, checkout/checkin |
| **User** | View and basic checkout/checkin |

---

## 🔒 Security Features

- **CSRF Protection** - All forms protected
- **Rate Limiting** - 50 requests/hour per IP
- **Secure Sessions** - HttpOnly, Secure, SameSite cookies
- **Input Validation** - SQLAlchemy ORM protection
- **XSS Protection** - Jinja2 auto-escaping
- **Audit Logging** - Complete activity trail

---

## 📦 Installation

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/KBM2.0.git
cd KBM2.0
```

### 2. Create Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
.venv\Scripts\activate     # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

### 5. Initialize Database

```bash
python setup_multitenant.py
```

### 6. Create App Admin

```bash
python create_admin.py
```

### 7. Run Application

```bash
python app_multitenant.py
```

Visit `http://localhost:5000`

---

## 🚀 Deployment

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete instructions covering:

- Docker deployment
- Traditional server deployment
- Cloud platforms (AWS, GCP, Azure)
- Nginx configuration
- SSL setup
- Backups and monitoring

---

## 📝 Configuration

### Environment Variables

**Production** (`.env.production`):
```bash
ENV=production
SECRET_KEY=<64-char-secure-key>
SESSION_COOKIE_SECURE=true
RATELIMIT_ENABLED=true
PORT=8000
```

**Development** (`.env.development`):
```bash
ENV=development
SECRET_KEY=dev-secret-key
DEBUG=true
PORT=5000
```

---

## 🧪 Testing

```bash
# Run all tests
pytest

# With coverage
pytest --cov=. --cov-report=html

# View coverage
open htmlcov/index.html
```

---

## 🐛 Troubleshooting

### App Won't Start

```bash
# Check Python version
python --version  # Must be 3.11+

# Reinstall dependencies
pip install -r requirements.txt

# Check database
ls -la KBM2_data/
```

### Docker Issues

```bash
# Rebuild containers
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check logs
docker-compose logs -f
```

See [USER_QUICKSTART_GUIDE.md](USER_QUICKSTART_GUIDE.md) troubleshooting section.

---

## 📊 Project Structure

```
KBM2.0/
├── app_multitenant.py     # Main entry point
├── config.py              # Configuration
├── requirements.txt       # Dependencies
├── entrypoint.sh          # Docker entrypoint
├── accounts/              # Tenant signup
├── auth/                  # Authentication
├── inventory/             # Core inventory
├── properties/            # Property management
├── utilities/             # Database and helpers
├── templates/             # HTML templates
├── static/                # CSS, JS
└── KBM2_data/             # Databases
```

See [PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md) for complete documentation.

---

## 🤝 Support

- **Documentation**: See links above
- **Issues**: GitHub Issues
- **Email**: support@yourcompany.com

---

## 📄 License

Proprietary - All Rights Reserved

---

## 🎉 Version

**Version**: 2.0
**Status**: Production Ready
**Last Updated**: 2025-10-20
**Security Review**: Completed ✅

---

For complete documentation, deployment instructions, and user guides, see the documentation files listed at the top of this README.
