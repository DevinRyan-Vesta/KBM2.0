# Creating App Admin Accounts

## Overview

App Admin accounts allow access to the application admin panel at the root domain where you can:
- Manage all tenant accounts
- View system-wide statistics
- Activate/deactivate tenants
- View all tenants' information

## Create App Admin (Docker - Production)

**Step 1: Access the Docker container**

```bash
cd /c/Users/dryan/KBM2.0
docker-compose exec python-app bash
```

**Step 2: Run the admin creation script**

```bash
python create_app_admin.py
```

**Step 3: Follow the interactive prompts**

The script will ask you for:
1. **Name**: Your full name (e.g., "Devin Ryan")
2. **Email**: Your email address (e.g., "devin@vestasells.com")
3. **PIN**: A secure 4-digit PIN
   - Avoid common PINs like 1234, 0000, 1111, etc.
   - The script will warn you about weak PINs
   - PIN will be hidden while typing (won't show on screen)
4. **Confirm PIN**: Enter the same PIN again to confirm

**Step 4: Exit the container**

```bash
exit
```

## Create App Admin (Local Development)

If running locally (not in Docker):

```bash
cd C:\Users\dryan\KBM2.0
python create_app_admin.py
```

Then follow the same prompts.

## Access the Admin Panel

After creating your admin account:

1. Navigate to: `http://localhost:8000/app-admin` (or your production domain)
2. Enter your email and PIN
3. Click "Sign In"

## Example Session

```
============================================================
KBM 2.0 - Create App Admin Account
============================================================

App Admins can:
  - Access the admin panel at the root domain
  - Manage all tenant accounts
  - View system-wide statistics

Enter admin name: Devin Ryan
Enter admin email: devin@vestasells.com

PIN Requirements:
  - Must be exactly 4 digits
  - Avoid simple patterns (1234, 0000, 1111, etc.)
  - Use a memorable but secure combination

Enter 4-digit PIN (hidden): ****
Confirm PIN (hidden): ****

Creating App Admin account...

============================================================
✅ App Admin Account Created Successfully!
============================================================
Name:  Devin Ryan
Email: devin@vestasells.com
PIN:   **** (hidden)
ID:    1

Access the admin panel at:
  https://yourdomain.com/app-admin

Login with:
  Email: devin@vestasells.com
  PIN:   (the PIN you just created)
```

## Security Best Practices

### Strong PIN Selection

**Good PINs** (examples of patterns to consider):
- Birth year last two digits + favorite number (e.g., 9427)
- Random but memorable combination (e.g., 8531)
- Date-based patterns only you know (e.g., 0615 for June 15th)

**Bad PINs** (avoid these):
- ❌ 1234 (most common)
- ❌ 0000, 1111, 2222, etc. (repeating digits)
- ❌ 0123, 4321 (sequential)
- ❌ Your birth year (too predictable)

### Additional Security

1. **Don't share your admin PIN** with anyone
2. **Use different PINs** for different accounts
3. **Change your PIN periodically** (every 3-6 months)
4. **Never write down your PIN** in plain text

## Managing Existing Admins

### List All App Admins

```bash
# Access Docker container
docker-compose exec python-app bash

# Run Python shell
python

# In Python:
from app_multitenant import create_app
from utilities.master_database import master_db, AppAdmin

app = create_app()
with app.app_context():
    admins = master_db.session.query(AppAdmin).all()
    for admin in admins:
        print(f"ID: {admin.id}, Name: {admin.name}, Email: {admin.email}")
```

### Reset Admin PIN

If you forget your PIN, you'll need to reset it manually:

```bash
# Access Docker container
docker-compose exec python-app bash

# Run Python shell
python

# In Python:
from app_multitenant import create_app
from utilities.master_database import master_db, AppAdmin

app = create_app()
with app.app_context():
    # Find admin by email
    admin = master_db.session.query(AppAdmin).filter_by(email='your@email.com').first()

    if admin:
        # Set new PIN
        admin.set_pin('5678')  # Replace with your new PIN
        master_db.session.commit()
        print(f"PIN reset for {admin.name}")
    else:
        print("Admin not found")
```

### Delete Admin Account

⚠️ **Warning**: This is permanent!

```bash
# Access Docker container
docker-compose exec python-app bash

# Run Python shell
python

# In Python:
from app_multitenant import create_app
from utilities.master_database import master_db, AppAdmin

app = create_app()
with app.app_context():
    # Find admin by email
    admin = master_db.session.query(AppAdmin).filter_by(email='old@email.com').first()

    if admin:
        master_db.session.delete(admin)
        master_db.session.commit()
        print(f"Deleted admin: {admin.name}")
```

## Troubleshooting

### "Admin with email already exists"

If you see this error, an admin with that email is already in the database. You can:

1. Use a different email address
2. Delete the existing admin (see above)
3. Reset the existing admin's PIN (see above)

### "Unable to connect to database"

Make sure:
1. You're running the command inside the Docker container (if using Docker)
2. The application has been properly initialized
3. The master database exists in `KBM2_data/master.db`

### "Permission denied"

If running locally, make sure:
1. The `KBM2_data` directory exists and is writable
2. You have permission to create files in the project directory

## Quick Reference

| Action | Command |
|--------|---------|
| **Create Admin (Docker)** | `docker-compose exec python-app python create_app_admin.py` |
| **Create Admin (Local)** | `python create_app_admin.py` |
| **Access Admin Panel** | Navigate to `/app-admin` on root domain |
| **List Admins** | Use Python shell commands (see above) |
| **Reset PIN** | Use Python shell commands (see above) |

---

**Last Updated**: 2025-10-20
**For**: KBM 2.0 Multi-Tenant Application
