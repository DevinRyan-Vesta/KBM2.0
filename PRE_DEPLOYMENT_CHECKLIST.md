# KBM 2.0 - Pre-Deployment Overview & Checklist

## Project Overview

**Key & Lockbox Management System (KBM) 2.0** is a multi-tenant web application for managing keys, lockboxes, signs, smart locks, and related inventory for property management businesses. The application features:

- **Multi-tenant Architecture**: Complete data isolation per tenant with subdomain-based routing
- **Master Database**: Central database for accounts and users
- **Tenant Databases**: Separate SQLite database per tenant for operational data
- **Role-Based Access Control**: Admin, Staff, and User roles with different permissions
- **Inventory Management**: Keys, lockboxes, signs (pieces and assembled units), smart locks
- **Checkout System**: Track item checkouts with receipts and activity logging
- **Property Management**: Properties, units, and contacts
- **Import/Export**: Bulk data operations with Excel support
- **Receipt Generation**: PDF receipts with barcodes
- **Activity Logging**: Comprehensive audit trail

## Technology Stack

- **Backend**: Flask 3.1.0 (Python 3.11+)
- **Database**: SQLite (development/small deployments), MySQL/PostgreSQL (production)
- **ORM**: SQLAlchemy 2.0.37 with Flask-SQLAlchemy
- **Authentication**: Flask-Login 0.6.3
- **Migrations**: Flask-Migrate 4.0.7 (Alembic)
- **Server**: Gunicorn 23.0.0 (production)
- **Document Generation**: ReportLab 4.2.5, python-barcode 0.16.1
- **Excel Processing**: openpyxl 3.1.5
- **Containerization**: Docker with multi-stage builds

## Current Status

### ✅ Completed Features

1. **Multi-tenant Infrastructure**
   - Subdomain routing (e.g., vesta.example.com)
   - Automatic tenant detection and database switching
   - Master and tenant database separation
   - Middleware for tenant context management

2. **Authentication & Authorization**
   - PIN-based login system
   - Role-based access control (admin, staff, user)
   - App admin system for platform management
   - Session management

3. **Inventory Management**
   - Keys with master key relationships
   - Lockboxes with code management
   - Signs (individual pieces and assembled units)
   - Smart locks with property/unit associations
   - Piece swapping for assembled signs

4. **Property Management**
   - Properties with multiple units
   - Unit details with view/edit/delete
   - Property-unit relationships

5. **Contact Management**
   - Contact types (tenant, owner, vendor, etc.)
   - Staff user associations

6. **Checkout System**
   - Quick checkout with autocomplete
   - Check-in functionality
   - Receipt generation with barcodes
   - Activity logging

7. **Import/Export**
   - Excel import with column mapping
   - Export functionality for inventory items

8. **UI/UX**
   - Theme-consistent styling
   - Dark mode support via CSS variables
   - Responsive design
   - Modal system for forms

### ⚠️ Critical Pre-Deployment Tasks

#### 1. Security Hardening

**CRITICAL**: The following security items MUST be addressed before production:

- [ ] **Secret Key**: Replace `SECRET_KEY=password123` in `.env.production` with a cryptographically secure random string
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

- [ ] **Database Passwords**: Update all database credentials
  - Current `.env.production` has placeholder credentials
  - Use strong passwords (16+ characters, mixed case, numbers, symbols)

- [ ] **Remove Debug Routes**: Delete or protect debug endpoints in `app_multitenant.py`:
  - `/debug/create-app-admin` (line 86)
  - `/debug/info` (line 110)
  - Or add IP whitelist/authentication

- [ ] **Environment Variables**: Never commit `.env` files
  - Add `.env*` to `.gitignore` (partially done, verify)
  - Use environment-specific files only on servers

- [ ] **HTTPS Configuration**: Enforce HTTPS in production
  - Configure reverse proxy (nginx/Apache)
  - Set secure cookie flags
  - Add HSTS headers

- [ ] **CSRF Protection**: Add Flask-WTF for CSRF tokens on forms

- [ ] **Rate Limiting**: Implement rate limiting for login attempts
  - Consider Flask-Limiter

- [ ] **Input Validation**: Review all form inputs for SQL injection protection
  - SQLAlchemy provides some protection, but validate user inputs

- [ ] **File Upload Security**: If file uploads are added, validate file types and sizes

#### 2. Missing Files for Deployment

- [ ] **Create `entrypoint.sh`**: Docker entrypoint script referenced in Dockerfile (line 67) but missing
  ```bash
  #!/bin/bash
  set -e

  # Run database migrations
  python -m flask db upgrade -d migrations_master

  # Start gunicorn
  exec gunicorn --bind 0.0.0.0:8000 --workers 4 --timeout 120 app_multitenant:app
  ```

- [ ] **Create `.dockerignore`**: Optimize Docker builds (partially exists, verify completeness)

- [ ] **Create production requirements**: Separate `requirements-dev.txt` and `requirements-prod.txt`

#### 3. Database Configuration

**SQLite Limitations in Production**:
- ⚠️ Current implementation uses SQLite for tenant databases
- SQLite has limitations:
  - No concurrent writes (locking issues)
  - File-based (not ideal for distributed systems)
  - Limited to single server

**Recommendations**:
- [ ] **For small deployments (< 10 users, single server)**: SQLite is acceptable
- [ ] **For production (> 10 users, multiple servers)**: Migrate to PostgreSQL or MySQL
  - Update `tenant_manager.py` to use PostgreSQL/MySQL for tenant databases
  - Configure connection pooling
  - Set up database backups

- [ ] **Database Backups**: Implement automated backup strategy
  ```bash
  # For SQLite
  sqlite3 KBM2_data/master.db ".backup backup_master.db"

  # For PostgreSQL
  pg_dump -U username dbname > backup.sql
  ```

- [ ] **Database Migrations**: Test migration scripts before deployment

#### 4. Configuration Management

- [ ] **Environment Detection**: Verify environment detection in `config.py`
  - Ensure `ENV` variable is set correctly on server
  - Test with `ENV=production`

- [ ] **Auto-Create Schema**: Set `AUTO_CREATE_SCHEMA=false` in production
  - Only enable for initial setup
  - Rely on migrations after that

- [ ] **Database URIs**: Configure production database URIs
  - Update `config.py` ProductionConfig
  - Use environment variables, not hardcoded values

- [ ] **Logging Configuration**: Configure production logging
  - Set appropriate log levels
  - Configure log rotation
  - Consider centralized logging (ELK, Splunk, etc.)

#### 5. Application Configuration

- [ ] **Session Configuration**: Configure secure sessions
  ```python
  app.config['SESSION_COOKIE_SECURE'] = True  # HTTPS only
  app.config['SESSION_COOKIE_HTTPONLY'] = True
  app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
  app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)
  ```

- [ ] **File Upload Limits**: Set maximum upload sizes
  ```python
  app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
  ```

- [ ] **Subdomain Configuration**: Configure allowed subdomains
  - Add validation for subdomain names
  - Reserve subdomains (www, admin, api, etc.)

#### 6. Infrastructure Requirements

- [ ] **Reverse Proxy**: Configure nginx or Apache
  - Handle HTTPS/SSL
  - Serve static files directly
  - Proxy to Gunicorn

- [ ] **Domain Configuration**:
  - Set up wildcard DNS (*.yourdomain.com)
  - Configure subdomain routing

- [ ] **Static File Serving**:
  - Configure nginx to serve /static/ directly
  - Consider CDN for production

- [ ] **Database Hosting**:
  - For PostgreSQL/MySQL: Set up managed database service or dedicated server
  - Configure connection pooling
  - Set up read replicas (if needed)

- [ ] **File Storage**:
  - Plan for persistent storage of tenant databases
  - Consider volume mounting for Docker
  - Plan backup storage location

#### 7. Monitoring & Observability

- [ ] **Application Monitoring**:
  - Add health check endpoint (exists at `/health`, verify functionality)
  - Monitor application errors
  - Track response times

- [ ] **Database Monitoring**:
  - Monitor database size and growth
  - Track query performance
  - Set up alerts for database issues

- [ ] **Log Aggregation**:
  - Configure log collection
  - Set up log rotation
  - Monitor error logs

- [ ] **Alerting**:
  - Set up alerts for critical errors
  - Monitor disk space (important for SQLite)
  - Track failed login attempts

#### 8. Testing Requirements

- [ ] **End-to-End Testing**: Test complete user workflows
  - Account creation
  - User login
  - Item checkout/checkin
  - Report generation
  - Import/export

- [ ] **Multi-Tenant Testing**: Verify tenant isolation
  - Create multiple tenants
  - Verify data separation
  - Test subdomain routing

- [ ] **Performance Testing**: Load test the application
  - Concurrent users
  - Database queries under load
  - Memory usage

- [ ] **Security Testing**:
  - Penetration testing
  - SQL injection attempts
  - XSS vulnerability scanning
  - Authentication bypass attempts

#### 9. Documentation Requirements

- [ ] **API Documentation**: Document all endpoints (if API is exposed)

- [ ] **Admin Documentation**: Document admin tasks
  - Creating accounts
  - User management
  - Database maintenance

- [ ] **Deployment Documentation**: Step-by-step deployment guide (creating separately)

- [ ] **Troubleshooting Guide**: Common issues and solutions

#### 10. Backup & Disaster Recovery

- [ ] **Backup Strategy**:
  - Automated daily backups of master database
  - Automated daily backups of all tenant databases
  - Test restoration procedures

- [ ] **Disaster Recovery Plan**:
  - Document recovery procedures
  - Set Recovery Time Objective (RTO)
  - Set Recovery Point Objective (RPO)
  - Test disaster recovery annually

- [ ] **Data Retention Policy**:
  - Define how long to keep activity logs
  - Plan for archiving old data
  - Define deletion policies

### 🔄 Recommended Improvements

#### Performance Optimizations

1. **Database Indexing**: Review and optimize database indexes
   - Add indexes on frequently queried columns
   - Monitor slow queries

2. **Caching**: Implement caching strategy
   - Redis for session storage
   - Cache frequently accessed data
   - Cache static content with proper headers

3. **Query Optimization**: Review SQLAlchemy queries
   - Use eager loading to prevent N+1 queries
   - Add pagination for large result sets

4. **Connection Pooling**: Configure SQLAlchemy connection pooling
   ```python
   app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
       'pool_size': 10,
       'pool_recycle': 3600,
       'pool_pre_ping': True
   }
   ```

#### Feature Enhancements

1. **Password Resets**: Add forgot password functionality
2. **Two-Factor Authentication**: Add 2FA for enhanced security
3. **API Development**: RESTful API for mobile apps or integrations
4. **Email Notifications**: Notify users of important events
5. **Advanced Reporting**: More detailed reports and analytics
6. **Bulk Operations**: Bulk checkout/checkin functionality
7. **Search Improvements**: Full-text search across inventory
8. **Audit Log UI**: Dedicated page for viewing activity logs
9. **User Preferences**: Theme selection, notification preferences
10. **Mobile Responsive**: Improve mobile experience

#### Code Quality

1. **Type Hints**: Add type hints throughout codebase
2. **Unit Tests**: Increase test coverage (currently minimal)
3. **Integration Tests**: Add more comprehensive integration tests
4. **Code Documentation**: Add docstrings to all functions
5. **Linting**: Set up pre-commit hooks with flake8/black
6. **Code Review**: Implement code review process

### 📋 Deployment Checklist Summary

Before deploying to production, ensure ALL items are checked:

**Critical Security** (Must Do):
- [ ] Generate secure SECRET_KEY
- [ ] Update all database passwords
- [ ] Remove or protect debug routes
- [ ] Configure HTTPS/SSL
- [ ] Add CSRF protection
- [ ] Implement rate limiting

**Infrastructure** (Must Do):
- [ ] Create entrypoint.sh file
- [ ] Configure reverse proxy (nginx/Apache)
- [ ] Set up wildcard DNS
- [ ] Configure environment variables
- [ ] Set up database backups
- [ ] Configure logging

**Testing** (Must Do):
- [ ] End-to-end testing
- [ ] Multi-tenant isolation testing
- [ ] Security testing
- [ ] Load testing

**Documentation** (Should Do):
- [ ] Admin documentation
- [ ] User documentation
- [ ] Troubleshooting guide

**Monitoring** (Should Do):
- [ ] Application monitoring
- [ ] Error tracking
- [ ] Performance monitoring

### 🚀 Next Steps

1. **Review this document** with your team
2. **Prioritize tasks** based on your deployment timeline
3. **Address critical security items** first
4. **Create entrypoint.sh** and other missing files
5. **Test thoroughly** in staging environment
6. **Follow the Deployment Guide** (separate document)
7. **Monitor closely** after deployment

### 📞 Post-Deployment

After deployment:
1. Monitor logs for errors
2. Verify all functionality works with real data
3. Test subdomain routing with actual domains
4. Perform security audit
5. Train users on the system
6. Establish regular backup verification
7. Set up monitoring dashboards

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20
**Author**: Claude (Anthropic)
**Project**: KBM 2.0 Multi-Tenant Application
