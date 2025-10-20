# KBM 2.0 - User Quickstart Guide

## Table of Contents

1. [Welcome to KBM 2.0](#welcome-to-kbm-20)
2. [Getting Started](#getting-started)
3. [Dashboard Overview](#dashboard-overview)
4. [Managing Keys](#managing-keys)
5. [Managing Lockboxes](#managing-lockboxes)
6. [Managing Signs](#managing-signs)
7. [Quick Checkout System](#quick-checkout-system)
8. [Properties and Units](#properties-and-units)
9. [Contact Management](#contact-management)
10. [Smart Locks](#smart-locks)
11. [Import and Export](#import-and-export)
12. [Reports and Activity Logs](#reports-and-activity-logs)
13. [User Management (Admins)](#user-management-admins)
14. [Tips and Best Practices](#tips-and-best-practices)
15. [Troubleshooting](#troubleshooting)

---

## Welcome to KBM 2.0

**Key & Lockbox Management System (KBM) 2.0** is your complete solution for managing keys, lockboxes, signs, and property access for your business. This guide will help you get up and running quickly.

### What Can KBM Do?

- Track keys, lockboxes, signs, and smart locks
- Check items in and out with receipt generation
- Manage properties and units
- Store contact information
- Generate reports and activity logs
- Import/export data to Excel
- Assemble and manage multi-piece signs
- Track master key relationships

### Who Uses KBM?

- **Property Management Companies**: Track keys and lockboxes across multiple properties
- **Real Estate Agencies**: Manage showing keys and lockboxes
- **Facility Managers**: Control access to buildings and units
- **Sign Companies**: Track sign inventory and assemblies

---

## Getting Started

### First Time Login

#### Step 1: Access Your KBM Account

Your company administrator will provide you with:
- **Website URL**: `https://yourcompany.example.com`
- **Your Email**: Your registered email address
- **Your PIN**: 4-digit PIN code

#### Step 2: Open the Login Page

1. Open your web browser (Chrome, Firefox, Safari, or Edge)
2. Navigate to your company's URL
3. You'll see the KBM login page

#### Step 3: Sign In

1. Enter your **email address**
2. Enter your **PIN code** (4 digits)
3. Click **Login**

**Note**: Your PIN is case-sensitive and must be exactly as provided.

#### Step 4: Explore the Dashboard

After logging in, you'll see your dashboard with:
- Recent activity
- Quick stats (total keys, lockboxes, signs)
- Quick access buttons

---

### Understanding User Roles

KBM has three user roles with different permissions:

| Role | Permissions |
|------|-------------|
| **Admin** | Full access: Manage all items, users, properties, settings |
| **Staff** | Most access: Manage items, checkout/checkin, view reports (cannot manage users) |
| **User** | Basic access: View items, checkout/checkin (limited editing) |

**Check Your Role**: Your role is displayed next to your name in the top right corner.

---

### Navigation

The main navigation menu is at the top of every page:

- **Home** - Dashboard
- **Inventory** - Keys, Lockboxes, Signs dropdown
- **Properties** - Manage properties and units
- **Contacts** - Contact management
- **Smart Locks** - Smart lock management
- **Reports** - Activity logs and reports
- **Users** - User management (Admins only)
- **Your Name** - Profile and logout

---

## Dashboard Overview

The dashboard is your command center. Here's what you'll see:

### Quick Stats Cards

- **Total Keys**: Number of keys in inventory
- **Total Lockboxes**: Number of lockboxes
- **Total Signs**: Number of signs (pieces + assembled units)
- **Checked Out**: Items currently checked out

### Quick Actions

- **Quick Checkout** - Fast checkout/checkin interface
- **Add Key** - Create new key
- **Add Lockbox** - Create new lockbox
- **Add Sign** - Create new sign piece

### Recent Activity

- Last 10 actions (checkouts, checkins, additions, edits)
- Who did what and when
- Click any item to view details

---

## Managing Keys

### Viewing Keys

1. Click **Inventory** → **Keys** in the navigation
2. You'll see a list of all keys with:
   - Custom ID (e.g., KA001, KA002)
   - Label (name/description)
   - Property/Unit (if assigned)
   - Location
   - Status (Available, Checked Out, Unavailable)

### Searching for Keys

Use the search bar at the top:
- Search by label, custom ID, location, or property
- Results update as you type

### Adding a New Key

#### Step 1: Open Add Key Form

1. Click **Inventory** → **Keys**
2. Click the **+ Add Key** button
3. The add key form appears

#### Step 2: Fill In Key Details

**Required Fields** (marked with *):
- **Label**: Descriptive name (e.g., "Front Door - Unit 101")

**Optional Fields**:
- **Property**: Select property from dropdown
- **Unit**: Select unit (filtered by property)
- **Location**: Where the key is stored (e.g., "Key Cabinet A")
- **Master Key**: Link to master key (if applicable)
- **Notes**: Additional information

**Tip**: Use clear, consistent naming. Good examples:
- "Main Entrance - Building A"
- "Mailbox Key - Unit 205"
- "Clubhouse - Pool Gate"

#### Step 3: Save the Key

1. Click **Add Key** button
2. Success message appears
3. Key is added with auto-generated ID (e.g., KA015)

### Editing a Key

1. Click **Inventory** → **Keys**
2. Find the key you want to edit
3. Click the key label or **View** button
4. On the details page, click **Edit**
5. Update the information
6. Click **Save Changes**

### Deleting a Key (Admins Only)

1. Go to the key details page
2. Click the **Delete** button (at the bottom)
3. Confirm deletion
4. **Warning**: This cannot be undone!

**Note**: You cannot delete a key that is currently checked out.

### Master Keys

**What is a Master Key?**
A master key opens multiple locks. In KBM, you can link keys to a master key to track relationships.

**Creating Master Key Relationships**:

1. Create the master key first (e.g., "Building Master")
2. When adding other keys, select the master key from the "Master Key" dropdown
3. On the master key's detail page, you'll see all keys that use it

**Viewing Master Key Information**:
- On any key linked to a master, you'll see "Master Key: [ID] - [Label]"
- Click the master key link to view its details
- The master key details show all "child" keys using it

---

## Managing Lockboxes

### Viewing Lockboxes

1. Click **Inventory** → **Lockboxes**
2. View all lockboxes with:
   - Custom ID (e.g., LB001)
   - Label
   - Current code
   - Property/Unit
   - Status

### Adding a Lockbox

1. Click **Inventory** → **Lockboxes**
2. Click **+ Add Lockbox**
3. Fill in:
   - **Label**: Name (e.g., "Front Door Lockbox")
   - **Initial Code**: 4-digit code (e.g., 1234)
   - **Location**: Where it's installed
   - **Property**: Associated property (optional)
   - **Address**: Property address
4. Click **Save**

**Note**: The code will be visible to users who view the lockbox details.

### Changing a Lockbox Code

1. Go to lockbox details page
2. Click **Edit**
3. Enter new code in the "Code" field
4. Click **Save Changes**
5. System logs the code change with timestamp

### Viewing Lockbox History

On the lockbox details page, scroll down to see:
- **Checkout History**: When and who checked it out
- **Activity Log**: All actions (edits, code changes, etc.)

---

## Managing Signs

Signs in KBM can be:
1. **Individual Pieces**: Frames, rider signs, bonus riders, etc.
2. **Assembled Units**: Complete signs built from multiple pieces

### Viewing Signs

1. Click **Inventory** → **Signs**
2. Filter by:
   - **All Signs**: Both pieces and assembled units
   - **Pieces**: Individual components
   - **Assembled Units**: Complete signs

### Adding a Sign Piece

#### Step 1: Open Add Sign Form

1. Click **Inventory** → **Signs**
2. Click **+ Add Sign** button

#### Step 2: Fill In Sign Details

- **Label**: Descriptive name (e.g., "Red Frame - Large")
- **Sign Type**: Select "Individual Piece"
- **Piece Type**: Select type:
  - Frame
  - Sign
  - Name Rider
  - Status Rider
  - Bonus Rider
  - Post
  - Other
- **Rider Text**: For name/status/bonus riders, enter text
- **Material**: E.g., "Aluminum", "Corrugated Plastic"
- **Condition**: New, Good, Fair, Poor
- **Location**: Storage location

#### Step 3: Save

Click **Add Sign** - Piece gets ID like S001, S002, etc.

### Building an Assembled Sign

**When to Use**: When you assemble a complete sign from multiple pieces.

#### Step 1: Open Sign Builder

1. Click **Inventory** → **Signs**
2. Click **Build Assembled Sign** button

#### Step 2: Select Pieces

1. Enter label for assembled unit (e.g., "123 Main St Sign")
2. Select pieces for each component:
   - **Frame** (required)
   - **Sign** (required)
   - **Name Rider** (optional)
   - **Status Rider** (optional)
   - **Bonus Rider** (optional)
   - **Post** (optional)

**Note**: Only available pieces (not already assigned) appear in dropdowns.

#### Step 3: Complete Assembly

1. Review selected pieces in summary
2. Fill in optional fields:
   - **Material**: Overall material
   - **Condition**: Overall condition
   - **Location**: Where assembled sign is stored/installed
3. Click **Build Assembled Sign**

Result:
- Assembled unit created with ID like ASA001
- All pieces marked as "Assigned" to this unit
- Pieces no longer available for other assemblies

### Viewing Assembled Sign Details

On assembled unit details page, you'll see:
- **Component Pieces**: Table of all pieces in the assembly
- **Disassemble Button**: Break assembly back into individual pieces
- **Swap Button**: Replace individual pieces (explained next)

### Swapping Sign Pieces

**Scenario**: A status rider on an assembled sign needs updating (e.g., "For Sale" → "Sold").

#### Step 1: View Assembled Sign

1. Go to **Inventory** → **Signs**
2. Find and click on the assembled unit
3. Scroll to "Component Pieces" section

#### Step 2: Swap Piece

1. Find the piece you want to replace
2. Click the **Swap** button next to it
3. A modal appears showing:
   - Current piece information
   - Dropdown of available replacement pieces (same type only)

#### Step 3: Select Replacement

1. Choose the new piece from dropdown
2. Click **Swap Piece**
3. Confirmation message appears

Result:
- Old piece becomes available again
- New piece assigned to the assembled unit
- Activity logged for audit trail

### Disassembling a Sign

**When to Use**: Breaking down an assembled sign back into individual pieces.

1. Go to assembled sign details page
2. Scroll to bottom
3. Click **Disassemble Sign**
4. Confirm disassembly

Result:
- Assembled unit deleted
- All pieces become available again

---

## Quick Checkout System

The Quick Checkout system is the fastest way to check items in and out.

### Opening Quick Checkout

**Method 1**: From Dashboard
- Click **Quick Checkout** button on dashboard

**Method 2**: From Navigation
- Click **Checkout** → **Quick Checkout**

**Method 3**: From Inventory
- On any inventory list (keys, lockboxes, signs)
- Click item's **Checkout** button

### Checking Out an Item

#### Step 1: Find the Item

1. Type in the search box:
   - Item label
   - Custom ID
   - Property name
2. Autocomplete suggestions appear
3. Click the item you want

#### Step 2: Review Item Preview

A preview appears showing:
- Item type and ID
- Label
- Property/Unit
- Current location
- Master key info (if applicable)

#### Step 3: Fill Out Checkout Form

- **Checked Out To**: Name of person receiving item (default: your name)
- **Location** (Optional): Where item is going
- **Notes** (Optional): Additional information

**Tip**: If checking out for yourself, "Checked Out To" auto-fills with your name.

#### Step 4: Complete Checkout

1. Click **Check Out** button
2. Success message appears
3. **Print Receipt** button appears

### Checking In an Item

#### Same Process as Checkout

1. Use quick checkout interface
2. Search for the item
3. Preview shows it's checked out
4. Click **Check In** button
5. Confirm checkin

Result:
- Item status returns to "Available"
- Return time recorded
- Receipt can be printed

### Printing Receipts

After checkout or checkin:
1. **Print Receipt** button appears
2. Click it to open receipt in new tab
3. Receipt shows:
   - Item information
   - Checkout/checkin details
   - Barcode (receipt ID)
   - Timestamp
4. Print using browser's print function (Ctrl+P / Cmd+P)

### Looking Up Old Receipts

1. Click **Reports** → **Receipt Lookup**
2. Enter receipt ID (from printed receipt)
3. Click **Look Up**
4. Receipt displays
5. Click **Print** to print again

---

## Properties and Units

### What Are Properties and Units?

- **Property**: A building or location (e.g., "Sunset Apartments")
- **Unit**: Individual spaces within a property (e.g., "Unit 101", "Unit 102")

Properties can have multiple units. Keys, lockboxes, and smart locks can be assigned to specific properties and units.

### Viewing Properties

1. Click **Properties** in navigation
2. View list of all properties
3. Click property name to view details

### Adding a Property

1. Click **Properties** → **Add New Property**
2. Fill in:
   - **Property Name**: Name (e.g., "Sunset Apartments")
   - **Property Type**: Residential, Commercial, Mixed Use, etc.
   - **Address Line 1**: Street address
   - **Address Line 2**: Apt/suite (optional)
   - **City, State, Postal Code**: Location details
   - **Country**: Default "USA"
   - **Notes**: Additional info
3. Click **Save Property**

### Adding Units to a Property

#### Method 1: From Property Details Page

1. Go to property details page
2. Scroll to "Units" section
3. Click **Add Unit** button
4. Fill in:
   - **Unit Label**: E.g., "101", "A", "Suite 200"
   - **Notes**: Additional info
5. Click **Add Unit**

#### Method 2: From Property Form

When creating a property, you can add units in the same form.

### Viewing Unit Details

1. Go to property details page
2. In the "Units" table, click unit label or **View** button
3. Unit details page shows:
   - Unit information
   - Associated keys
   - Associated lockboxes
   - Associated smart locks

### Editing a Unit

1. Go to unit details page
2. Click **Edit** button
3. Update information
4. Click **Save Changes**

### Deleting a Unit (Admins Only)

1. Go to unit details page
2. Click **Delete** button
3. Confirm deletion

**Warning**: Cannot delete unit if it has associated keys/lockboxes/smart locks.

---

## Contact Management

Store information about tenants, property owners, vendors, and other contacts.

### Viewing Contacts

1. Click **Contacts** in navigation
2. View all contacts with search and filtering

### Adding a Contact

1. Click **Contacts** → **Add Contact**
2. Fill in:
   - **Name**: Full name
   - **Type**: Tenant, Owner, Vendor, Agent, Emergency, Other
   - **Company**: Company name (if applicable)
   - **Email**: Email address
   - **Phone**: Phone number
   - **Staff User**: Link to KBM user (if applicable)
   - **Notes**: Additional information
3. Click **Save Contact**

### Editing a Contact

1. Click contact name from list
2. Click **Edit** button
3. Update information
4. Click **Save Changes**

### Deleting a Contact

1. Go to contact details page
2. Click **Delete** button
3. Confirm deletion

---

## Smart Locks

Manage digital/smart locks with access codes.

### Viewing Smart Locks

1. Click **Smart Locks** in navigation
2. View all smart locks

### Adding a Smart Lock

1. Click **Smart Locks** → **Add Smart Lock**
2. Fill in:
   - **Label**: Name (e.g., "Front Door Smart Lock")
   - **Provider**: Brand (e.g., "August", "Schlage")
   - **Primary Code**: Main access code
   - **Backup Code**: Emergency code
   - **Property**: Associated property
   - **Unit**: Associated unit
   - **Instructions**: Usage instructions
   - **Notes**: Additional info
3. Click **Save Smart Lock**

### Editing Smart Lock Codes

1. Go to smart lock details
2. Click **Edit**
3. Update codes
4. Click **Save Changes**

**Security Note**: Codes are visible to anyone who can view the smart lock. Ensure only authorized users have access.

---

## Import and Export

### Exporting Data

Export inventory to Excel for backup or reporting.

#### Step 1: Choose Export Type

1. Click **Exports** in navigation (or **Inventory** → **Export**)
2. Choose what to export:
   - **Keys**
   - **Lockboxes**
   - **Signs**

#### Step 2: Download File

1. Click the export button
2. Excel file downloads automatically
3. Open in Microsoft Excel, Google Sheets, or LibreOffice

**File Contents**:
- All item data in spreadsheet format
- One row per item
- Columns for all attributes

### Importing Data

Bulk add items from Excel spreadsheet.

#### Step 1: Prepare Your File

Create Excel file (.xlsx) with columns for:
- Keys: label, location, property, unit, notes, etc.
- Lockboxes: label, code, location, property, etc.
- Signs: label, piece_type, material, condition, etc.

**Tip**: Export existing data first to see the expected format.

#### Step 2: Upload File

1. Click **Inventory** → **Import** → **(Keys/Lockboxes/Signs)**
2. Click **Choose File**
3. Select your Excel file
4. Click **Upload**

#### Step 3: Map Columns

1. System detects columns in your file
2. Map each column to the correct database field
   - Left side: Database fields
   - Right side: Your file columns
3. Required fields marked with *
4. System auto-matches similar column names
5. Review and adjust mappings
6. Click **Next**

#### Step 4: Preview Import

1. Review first 5 rows
2. Check that data looks correct
3. If errors, go back and remap
4. Click **Import Data**

#### Step 5: Confirmation

1. Import processes
2. Success message shows number of items imported
3. Any errors are displayed
4. Click **View Inventory** to see imported items

**Tips**:
- Keep file under 1000 rows for best performance
- Ensure property/unit names match existing ones exactly
- Leave optional fields blank if no data

---

## Reports and Activity Logs

### Viewing Activity Logs

Activity logs track all actions in the system.

#### Step 1: Open Activity Log

1. Click **Reports** → **Activity Log**
2. Or from dashboard, click **View All Activity**

#### Step 2: Review Activities

View:
- **Action**: What happened (e.g., "key_checked_out", "lockbox_created")
- **User**: Who performed the action
- **Target**: What item was affected
- **Summary**: Human-readable description
- **Timestamp**: When it occurred

#### Step 3: Filter Activities

- Use search box to filter by:
  - User name
  - Action type
  - Item name
- Activities update as you type

### Common Activity Actions

- `key_created` - New key added
- `key_checked_out` - Key checked out
- `key_checked_in` - Key returned
- `key_edited` - Key information updated
- `key_deleted` - Key removed
- `lockbox_created` - New lockbox added
- `lockbox_code_changed` - Lockbox code updated
- `sign_assembled` - Assembled sign built
- `sign_piece_swapped` - Sign piece replaced
- `user_login` - User logged in

### Generating Reports

1. Click **Reports** in navigation
2. Choose report type (if available):
   - Inventory summary
   - Checkout history
   - User activity
3. Select date range or filters
4. Click **Generate Report**
5. View or export report

**Note**: Specific report types may vary based on your installation.

---

## User Management (Admins)

Admin users can create and manage other users.

### Viewing Users

1. Click **Users** in navigation (Admins only)
2. View all users with:
   - Name
   - Email
   - Role
   - Status (Active/Inactive)

### Adding a User

#### Step 1: Open User Form

1. Click **Users** → **Add User**

#### Step 2: Fill In User Details

- **Name**: Full name
- **Email**: Email address (used for login)
- **PIN**: 4-digit numeric PIN (used for login)
- **Role**: Select Admin, Staff, or User
- **Status**: Active (check to enable login)

**Important**: Email must be unique.

#### Step 3: Save User

1. Click **Create User**
2. Success message appears
3. Share login credentials with user:
   - Website URL
   - Email
   - PIN

**Security Tip**: Have user change PIN after first login (if supported).

### Editing a User

1. Click **Users**
2. Click user's name
3. Click **Edit** button
4. Update information
5. **Leave PIN blank** to keep current PIN
6. **Enter new PIN** to change it
7. Click **Save Changes**

### Changing User Role

1. Go to user edit page
2. Change **Role** dropdown
3. Click **Save Changes**

**Role Permissions**:
- **Admin**: Can manage everything including users
- **Staff**: Can manage items, checkout/checkin, but not users
- **User**: Can view and checkout/checkin, limited editing

### Deactivating a User

1. Go to user edit page
2. Uncheck **Active** status
3. Click **Save Changes**

Result: User cannot log in anymore.

**Note**: This does not delete the user. Their historical activity remains.

---

## Tips and Best Practices

### Inventory Management

1. **Consistent Naming**: Use clear, consistent names
   - Good: "Front Door - Unit 101"
   - Bad: "Key 1"

2. **Use Locations**: Always specify where items are stored
   - Helps find items quickly
   - Examples: "Key Cabinet A - Row 3", "Office Drawer"

3. **Link to Properties**: Assign items to properties/units
   - Makes searching easier
   - Provides better organization
   - Useful for reports

4. **Regular Audits**: Periodically verify:
   - Items are where location says
   - Checked out items are actually out
   - Inventory counts match reality

### Checkout Management

1. **Always Check In**: Don't forget to check items back in
   - Keeps inventory accurate
   - Shows availability to others

2. **Add Notes**: Include useful information
   - Where item is going
   - Expected return date
   - Special instructions

3. **Print Receipts**: Keep paper trail
   - Helps with disputes
   - Easy reference for item ID

### Security

1. **Use Strong PINs**: Avoid simple PINs like 1234
   - Use random 4-digit numbers
   - Don't share PINs

2. **Limit Access**: Assign appropriate roles
   - Not everyone needs admin access
   - Use Staff role for most employees

3. **Review Activity Logs**: Check regularly for:
   - Unusual activity
   - Missing items
   - Unauthorized access

4. **Update Codes**: Change lockbox codes periodically
   - After terminations
   - Every 3-6 months
   - After security incidents

### Data Management

1. **Export Regularly**: Backup your data
   - Export to Excel monthly
   - Store backups securely
   - Test restores occasionally

2. **Clean Up Old Data**: Remove:
   - Deleted/lost items
   - Inactive users
   - Old contacts

3. **Import Carefully**: When importing:
   - Test with small file first
   - Review preview before importing
   - Keep original file as backup

---

## Troubleshooting

### I Forgot My PIN

**Solution**: Contact your administrator to reset your PIN.

Admin can:
1. Go to **Users**
2. Click your name
3. Click **Edit**
4. Enter new PIN
5. Share new PIN with you

---

### I Can't Find an Item

**Troubleshooting Steps**:

1. **Check Search Terms**: Try different keywords
   - Search by ID, label, location, property

2. **Check Filters**: Ensure no filters are active
   - Look for "All", "Available", "Checked Out" filters

3. **Check Status**: Item might be checked out
   - Look in "Checked Out" filter
   - Search by person who checked it out

4. **Check Spelling**: Verify spelling in search

5. **Ask Admin**: Admin can search across all items

---

### Checkout Button is Disabled

**Possible Reasons**:

1. **Item Already Checked Out**: Can't check out twice
   - Someone else has it
   - Check in first, then check out

2. **Item Status is Unavailable**: Set to unavailable
   - Admin needs to change status

3. **Insufficient Permissions**: User role limitation
   - Contact admin for role upgrade

---

### Import Failed

**Common Issues**:

1. **Wrong File Format**: Must be .xlsx (Excel 2007+)
   - Convert old .xls files to .xlsx
   - CSV files not supported

2. **Missing Required Fields**: Must have required data
   - Check column mappings
   - Ensure required fields have data

3. **Invalid Data**: Check for:
   - Empty labels
   - Invalid property names
   - Text in number fields

4. **File Too Large**: Keep under 1000 rows
   - Split into multiple files
   - Import in batches

---

### Page Won't Load

**Solutions**:

1. **Refresh Page**: Press F5 or Ctrl+R (Cmd+R on Mac)

2. **Clear Browser Cache**:
   - Chrome: Ctrl+Shift+Delete
   - Firefox: Ctrl+Shift+Delete
   - Safari: Cmd+Option+E

3. **Try Different Browser**: Use Chrome, Firefox, or Edge

4. **Check Internet**: Verify internet connection

5. **Contact IT**: If persists, contact your IT department

---

### I See an Error Message

**General Steps**:

1. **Read the Error**: Error messages usually explain the problem
   - "Item not found" - Item was deleted
   - "Duplicate email" - Email already in use
   - "Permission denied" - Insufficient role

2. **Take Screenshot**: Capture error for support

3. **Try Again**: Sometimes temporary glitch
   - Refresh page
   - Try action again

4. **Contact Admin**: If error persists
   - Provide screenshot
   - Explain what you were doing
   - Note any error codes

---

## Getting Help

### Built-In Help

- **Tooltips**: Hover over fields for hints
- **Required Fields**: Marked with * asterisk
- **Validation**: Forms show errors before saving

### Contact Your Administrator

For help with:
- Forgot PIN
- Permission issues
- Missing features
- Data problems

### Technical Support

If your administrator cannot help:
- Contact your KBM support team
- Provide:
  - Your company subdomain
  - Description of issue
  - Screenshots of errors
  - Steps to reproduce

---

## Keyboard Shortcuts

**General**:
- `Ctrl+F` or `Cmd+F` - Focus search box (on list pages)

**Forms**:
- `Tab` - Move to next field
- `Shift+Tab` - Move to previous field
- `Enter` - Submit form (some forms)
- `Esc` - Close modal (on modal forms)

---

## Mobile Usage

KBM works on mobile devices (phones, tablets):

**Best Practices**:
- Use landscape mode for better view
- Tap "Request Desktop Site" if mobile view has issues
- Use search instead of scrolling long lists
- Quick checkout works great on mobile

---

## Updates and New Features

KBM is continuously improved. New features may be added over time.

**Stay Informed**:
- Watch for notification banners
- Check dashboard for announcements
- Ask admin about new features

---

## Conclusion

Congratulations! You now know how to use KBM 2.0 effectively.

**Quick Recap**:
1. Log in with email and PIN
2. Use dashboard for quick access
3. Manage keys, lockboxes, signs via Inventory menu
4. Quick checkout for fast check-out/check-in
5. Assign items to properties and units
6. Store contacts for reference
7. Import/export for bulk operations
8. Review activity logs for audit trail
9. Admins manage users and permissions

**Remember**:
- Check items in promptly
- Use clear, consistent naming
- Print receipts for records
- Review activity logs regularly
- Contact admin for help

Thank you for using KBM 2.0!

---

**Document Version**: 1.0
**Last Updated**: 2025-10-20
**Author**: Claude (Anthropic)
**Project**: KBM 2.0 Multi-Tenant Application

**Feedback**: Please report any issues or suggestions to your system administrator.
