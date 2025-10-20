# Login Credentials for Testing

## ✅ FIXED: DateTime Error
The `datetime.UTC` error has been resolved. Login should now work correctly.

## Test Accounts

### 1. Demo Tenant Account
**URL:** http://demo.localhost:5000
- **Email:** admin@demo.com
- **PIN:** `5678`
- **Role:** Admin
- **Database:** `KBM2_data/tenants/demo.db`

### 2. App Admin Account (System Administrator)
**URL:** http://localhost:5000/auth/login
- **Email:** admin@test.com
- **PIN:** `1234`
- **Role:** App Admin
- **Access:** Can manage all accounts

## How to Test

### Test Demo Tenant Login:
1. Open browser: `http://demo.localhost:5000`
2. Enter PIN: `5678`
3. Click "Sign In"
4. ✅ You should be logged in to the demo company

### Test App Admin Login:
1. Open browser: `http://localhost:5000/auth/login`
2. Enter PIN: `1234`
3. Click "Sign In"
4. ✅ You should see the app admin dashboard

### Create Your Own Account:
1. Open browser: `http://localhost:5000/accounts/signup`
2. Fill in the form:
   - **Company Name:** Your Company Name
   - **Subdomain:** yourcompany (lowercase, no spaces)
   - **Your Name:** Your Name
   - **Email:** your@email.com
   - **PIN:** Your secure PIN (4+ characters)
   - **Confirm PIN:** Same PIN again
3. Click "Create Account"
4. ✅ You'll be redirected to `http://yourcompany.localhost:5000`
5. Log in with your PIN

## Server Status

The server is running on: `http://localhost:5000`

**Server must be running** for login to work:
```bash
python app_multitenant.py
```

## Troubleshooting

### "Invalid PIN" error
- Make sure you're using the correct PIN for the account
- Demo: `5678`
- App Admin: `1234`

### Can't access `demo.localhost`
- Try using `demo.lvh.me:5000` instead (resolves to 127.0.0.1)
- Or add to hosts file: `127.0.0.1 demo.localhost`

### Still getting datetime errors
- Make sure the server has restarted after the fix
- Check server logs for any other errors

## What Works After Login

Once logged in to a tenant (e.g., demo.localhost):
- ✅ Dashboard/home page
- ✅ User management (for admins)
- ⚠️ Inventory - needs update for multi-tenant
- ⚠️ Checkout - needs update for multi-tenant
- ⚠️ Contacts - needs update for multi-tenant
- ⚠️ Properties - needs update for multi-tenant

The inventory, checkout, contacts, and properties pages will need updates to use tenant-aware queries. The core authentication and routing is working!

## Next Steps After Successful Login

1. Test creating items (may have database errors - normal)
2. Test checking out items (may have database errors - normal)
3. Let me know which features you want to prioritize for multi-tenant updates

The datetime issue is **FIXED** and login should work now! 🎉
