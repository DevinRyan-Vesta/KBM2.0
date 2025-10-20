# KBM2.0
2.0 Remake of keybox manager program
Here’s an updated and comprehensive **overview** of your program, incorporating everything discussed so far:

---

## **Keybox Manager Program Overview**

### **1. Goals**
- Manage office staff checking out keys, lockboxes, and signs.
- Track item availability, assignments, and locations.
- Ensure scalability, accountability, and ease of use.
- Integrate barcode and image handling for streamlined workflows.
- Sync local data with Google Sheets to maintain accessibility and redundancy.

---

### **2. Core Features**

#### **Authentication and User Management**
- **User Roles**: Admin, Office Staff, Agent.
- **Features**:
  - Admins can:
    - Create/manage users, assign roles, and update PINs.
    - Modify or remove other Admin roles only with a **Master PIN**.
  - Users can:
    - Change their PIN, upload profile pictures, and view their activity logs.
  - Sessions:
    - Expire after 5 minutes of inactivity on shared office terminals.
    - Persist for 30 days on personal devices.
    - Include a "Log out of all devices" option on the profile page.
  - Email addresses are tied to accounts for notifications (not login).

#### **Item Management**
- **Item Details**:
  - Each item includes:
    - Barcode, Image, Type (Keys, Lockboxes, Signs), Status, Quantity, Assignment Info.
  - Barcodes follow the format: `1_2345` (type + unique ID). No length limits to support scalability.
  - Images are stored locally initially, with plans to switch to cloud storage in the future.
- **Permissions**:
  - All users can:
    - Add new items individually.
    - Edit items (with detailed logs of changes).
  - Admins can:
    - Add items in bulk via CSV.
    - Delete items.
- **Quantity Handling**:
  - Multiple users can check out a quantity of the same item (e.g., 3 out of 10 keys).
  - Quantities can also be assigned for long-term use.

#### **Barcode and Image Management**
- Barcodes:
  - Automatically generated for items.
  - Saved locally as PNGs.
  - Printable directly from the app or downloadable for manual printing.
- Images:
  - Uploaded locally for each item.
  - Stored in a structured directory, with paths saved in the database.

#### **Logging and Accountability**
- Maintain transaction logs for:
  - User actions (login/logout, profile updates).
  - Item actions (add, edit, delete).
  - Check-in/out actions (linked to the Checkout System).
- Logs can be:
  - Filtered by user, item, or action type.
  - Exported as CSV or PDF for reports.

#### **Checkout System**
- Allow users to:
  - Check out items using barcodes or manual entry.
  - Return items and update their statuses.
- Include alerts for:
  - Overdue items (with optional reminders via email or dashboard).
  - Long-term assignments excluded from overdue status.

#### **Google Sheets Integration**
- Sync local database with Google Sheets:
  - Triggered hourly or during user login.
  - Include all relevant data (items, transactions, users).
- Validate sync status and retry on failures.

---

### **3. APIs**

#### **Authentication APIs**
| Endpoint                 | Method | Description                                |
|--------------------------|--------|--------------------------------------------|
| `/auth/login`            | POST   | Login with PIN and start a session.        |
| `/auth/logout`           | POST   | End the current session.                   |
| `/auth/logout-all`       | POST   | Log out from all active devices.           |
| `/auth/create-user`      | POST   | Add a new user.                            |
| `/auth/update-user`      | PATCH  | Update user info (e.g., role, PIN).        |
| `/auth/delete-user`      | DELETE | Remove a user.                             |

#### **Item Management APIs**
| Endpoint                 | Method | Description                                |
|--------------------------|--------|--------------------------------------------|
| `/items`                 | GET    | Fetch all items (filterable by type/status). |
| `/items/<item_id>`       | GET    | Fetch details of a specific item.          |
| `/items/add`             | POST   | Add a new item (with image and barcode).   |
| `/items/edit/<item_id>`  | PATCH  | Update an item’s details.                  |
| `/items/bulk-add`        | POST   | Bulk upload items via CSV.                 |
| `/items/delete/<item_id>`| DELETE | Remove an item.                            |

#### **Barcode and Image Management APIs**
| Endpoint                       | Method | Description                                |
|--------------------------------|--------|--------------------------------------------|
| `/items/generate-barcode`      | POST   | Generate and save a barcode for an item.   |
| `/items/upload-image`          | POST   | Upload and store an image for an item.     |
| `/items/get-barcode/<item_id>` | GET    | Fetch the barcode image for an item.       |
| `/items/get-image/<item_id>`   | GET    | Fetch the item image.                      |

#### **Checkout System APIs**
| Endpoint                 | Method | Description                                |
|--------------------------|--------|--------------------------------------------|
| `/checkout`              | POST   | Check out an item (barcode or manual).     |
| `/return`                | POST   | Return an item.                            |
| `/overdue-items`         | GET    | List all overdue items.                    |

#### **Google Sheets Integration APIs**
| Endpoint                 | Method | Description                                |
|--------------------------|--------|--------------------------------------------|
| `/sync`                  | POST   | Trigger manual synchronization.            |
| `/sync-status`           | GET    | Get the last sync time and status.         |

#### **Reports and Logs APIs**
| Endpoint                  | Method | Description                                |
|---------------------------|--------|--------------------------------------------|
| `/logs/user-actions`      | GET    | Fetch logs of user actions.                |
| `/logs/item-actions`      | GET    | Fetch logs of item actions.                |
| `/logs/export`            | GET    | Export logs to CSV or PDF.                 |

---

### **4. Database Schema**

#### **Users Table**
| Field          | Type         | Description                           |
|----------------|--------------|---------------------------------------|
| `id`           | Integer (PK) | Unique user ID.                      |
| `name`         | Text         | Full name.                           |
| `pin`          | Text         | Encrypted PIN for login.             |
| `email`        | Text         | User email.                          |
| `role`         | Text         | Role (Admin, Office, Agent).         |
| `profile_pic`  | Text         | Path to profile picture.             |

#### **Items Table**
| Field          | Type         | Description                           |
|----------------|--------------|---------------------------------------|
| `id`           | Integer (PK) | Unique item ID.                      |
| `type`         | Text         | Item type (Key, Lockbox, Sign).       |
| `barcode`      | Text         | Barcode for scanning.                |
| `image`        | Text         | Path to item image.                  |
| `total_quantity`| Integer     | Total available quantity.            |
| `checked_out`  | JSON         | List of users with quantities checked out. |
| `assigned`     | JSON         | Assigned quantities.                 |

#### **Transactions Table**
| Field          | Type         | Description                           |
|----------------|--------------|---------------------------------------|
| `id`           | Integer (PK) | Unique transaction ID.               |
| `user_id`      | Integer (FK) | ID of the user performing the action. |
| `item_id`      | Integer (FK) | ID of the item being checked out.     |
| `action`       | Text         | Action type (Checkout, Return, etc.). |
| `timestamp`    | DateTime     | Time of the action.                   |
| `notes`        | Text         | Additional notes.                     |

---

### **Next Steps**
1. Finalize database schema and APIs.
2. Begin implementing Flask blueprints for modular development.
3. Test barcode/image handling and printing workflows.
4. Design a clean, user-friendly frontend.
