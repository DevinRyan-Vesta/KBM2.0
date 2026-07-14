# KBM API Documentation

Integration guide for the KBM REST API — connect your own apps, scripts,
Zapier/Make workflows, or property-management tools to KBM.

**Live, always-current references** (served by the app itself):

- **Interactive docs**: `https://<your-subdomain>.<your-domain>/api/v1/docs`
- **OpenAPI 3.0 spec**: `https://<your-subdomain>.<your-domain>/api/v1/openapi.json`
  (import this into Postman, Insomnia, or a code generator)

This document is the narrative companion: concepts, auth walkthrough, and
copy-paste examples.

---

## 1. The Basics

### Base URL

Every tenant (company) has its own subdomain, and the API is scoped the same
way as the web app:

```
https://<your-subdomain>.<your-domain>/api/v1
```

Calling a tenant endpoint on the wrong subdomain returns `403 wrong_tenant`;
calling it on the root domain returns `404 tenant_required`.

### Content type

Send request bodies as JSON with `Content-Type: application/json`. All
responses are JSON.

### Versioning

The API is versioned in the URL (`/api/v1`). Backwards-incompatible changes
will ship as `/api/v2`; `v1` responses may gain *new* fields at any time, so
parse leniently.

---

## 2. Authentication

### Step 1 — create a token

Exchange your normal KBM login (email + PIN) for a long-lived API token.
This is the only endpoint that takes credentials; it is rate-limited
(10/minute, 30/hour).

```bash
curl -X POST https://acme.example.com/api/v1/auth/tokens \
  -H "Content-Type: application/json" \
  -d '{
        "email": "you@acme.com",
        "pin": "1234",
        "name": "zapier-integration",
        "expires_in_days": 365
      }'
```

```json
{
  "id": 7,
  "name": "zapier-integration",
  "token": "kbm_1a2b3c4d_Xy9...longsecret...",
  "token_prefix": "1a2b3c4d",
  "expires_at": "2027-07-13T00:00:00",
  "created_at": "2026-07-13T18:04:00",
  "last_used_at": null,
  "revoked": false
}
```

> ⚠️ **The `token` value is shown exactly once.** Store it in a secret
> manager. Only a hash is kept server-side; a lost token cannot be
> recovered — revoke it and create a new one.

`name` and `expires_in_days` are optional (`expires_in_days` omitted = the
token never expires). Each user can hold up to 25 active tokens.

### Step 2 — use it

Send the token on every request:

```
Authorization: Bearer kbm_1a2b3c4d_Xy9...
```

Tokens inherit the **role of the user who created them**:

| Role | Can |
|------|-----|
| user / staff / agent | Read everything, create/update records, checkout/checkin/assign |
| admin / owner | All of the above + deletes, user management, settings, activity logs |
| app_admin | Cross-tenant access + `GET /accounts` on the root domain |

### Managing tokens

```bash
# List tokens (admins see the whole account's tokens)
curl https://acme.example.com/api/v1/auth/tokens -H "Authorization: Bearer $TOKEN"

# Revoke one (takes effect immediately)
curl -X DELETE https://acme.example.com/api/v1/auth/tokens/7 -H "Authorization: Bearer $TOKEN"

# Sanity-check your credentials
curl https://acme.example.com/api/v1/me -H "Authorization: Bearer $TOKEN"
```

Deactivating a user in KBM instantly invalidates all of their tokens.

---

## 3. Conventions

### Errors

Every error is JSON with a stable machine-readable code:

```json
{ "error": { "code": "no_copies_available", "message": "Invalid number of copies. Available: 2." } }
```

| HTTP | Typical codes |
|------|---------------|
| 400 | `invalid_json`, `invalid_field`, `unknown_fields`, `missing_credentials` |
| 401 | `missing_token`, `invalid_token`, `token_revoked`, `user_inactive`, `invalid_credentials` |
| 403 | `wrong_tenant`, `admin_required`, `forbidden` |
| 404 | `not_found`, `tenant_required` |
| 409 | `duplicate_custom_id`, `duplicate_email`, `no_copies_available`, `item_in_use`, `property_in_use`, `contact_in_use`, `token_limit`, `user_limit` |
| 429 | `rate_limited` |

### Pagination

All list endpoints accept `page` (default 1) and `per_page` (default 25,
max 100) and return:

```json
{
  "items": [ ... ],
  "pagination": { "page": 1, "per_page": 25, "total": 132, "pages": 6 }
}
```

### Dates

Send dates as `YYYY-MM-DD` (or full ISO-8601). All returned timestamps are
naive UTC ISO-8601.

### Item references

Anywhere the path contains `{item_ref}` you may use **either** the numeric
database id (`42`) or the human-facing custom id (`KA042`, `LBA001`,
`SA003`) — case-insensitive.

---

## 4. Resources

### Items (keys, lockboxes, signs)

```
GET    /items                      list — filters: type, status, q, property_id, assigned_to
POST   /items                      create ('type' + 'label' required; custom_id auto-generated)
GET    /items/{item_ref}           detail incl. active_checkouts
PATCH  /items/{item_ref}           update descriptive fields
DELETE /items/{item_ref}           admin; blocked while checked out / assigned
POST   /items/{item_ref}/checkout
POST   /items/{item_ref}/checkin
POST   /items/{item_ref}/assign
```

`status` is managed by the action endpoints — you cannot PATCH it. Each type
accepts only its own fields (`unknown_fields` otherwise):

| Type | Extra writable fields |
|------|----------------------|
| all | `label`, `location`, `address`, `assigned_to` |
| Lockbox | `code_current`, `code_previous`, `supra_id` |
| Key | `key_hook_number`, `keycode`, `total_copies`, `checkout_purpose`, `master_key_id` |
| Sign | `sign_subtype` (Piece \| Assembled Unit), `piece_type`, `rider_text`, `material`, `condition` |

**Create a key:**

```bash
curl -X POST https://acme.example.com/api/v1/items \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"type": "Key", "label": "Front Door — 123 Main St", "total_copies": 5, "key_hook_number": "H12"}'
```

**Check out 2 copies of a key** (creates a checkout record; sends the
tenant's usual email notification if the contact has an email):

```bash
curl -X POST https://acme.example.com/api/v1/items/KA001/checkout \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"copies": 2, "checked_out_to": "Jane Contractor", "purpose": "Showing",
       "expected_return_date": "2026-07-20", "contact_id": 14}'
```

Returns `201` with `item` and the `checkout` record — keep `checkout.id` to
check that specific loan back in:

```bash
curl -X POST https://acme.example.com/api/v1/items/KA001/checkin \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"checkout_id": 55}'
```

**Lockboxes require the current code on checkout *and* check-in** — the API
rotates `code_current` → `code_previous` exactly like the web app:

```bash
curl -X POST https://acme.example.com/api/v1/items/LBA001/checkout \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"code": "4482", "assigned_to": "Agent Bob", "address": "123 Main St"}'
```

**Assignments** (longer-term than a checkout). Keys require
`assignment_type` = `tenant` | `contractor` | `property`; contractor
assignments require `expected_return_date`; property assignments require
`property_id` (and `assigned_to` defaults to the property's name):

```bash
curl -X POST https://acme.example.com/api/v1/items/KA001/assign \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"assignment_type": "property", "property_id": 3, "copies": 1}'
```

### Checkouts (history)

```
GET /checkouts        filters: active, overdue, item_id, contact_id, person
GET /checkouts/{id}
```

`GET /checkouts?overdue=true` is the one to poll for reminder workflows —
active checkouts past their expected return date.

### Properties & units

```
GET/POST   /properties                     (q filter searches name/address/city)
GET/PATCH/DELETE /properties/{id}          (GET includes units + item counts)
GET/POST   /properties/{id}/units
GET/PATCH/DELETE /units/{unit_id}
```

`name` and `address_line1` are required on create. Deleting is blocked while
items are linked (`409 property_in_use`).

### Contacts

```
GET/POST   /contacts                       (q searches name/company/email/phone; type filter)
GET/PATCH/DELETE /contacts/{id}            (GET includes active_checkouts)
```

Pass a `contact_id` when checking out keys to link the loan to a contact —
that link powers email notifications and the contact's checkout history.

### Smart locks

```
GET/POST   /smart-locks                    (q, property_id filters)
GET/PATCH/DELETE /smart-locks/{id}         (GET includes image metadata)
```

`label` and `code` are required. Image *uploads* are web-only.

### Audits (read-only)

```
GET /audits                                (status filter: pending|in_progress|completed)
GET /audits/{id}                           items + discrepancy_count
```

### Admin (admin/owner tokens)

```
GET/POST /users            PATCH/DELETE /users/{id}     manage account users
GET/PATCH /settings                                     tenant settings (notifications, thresholds, receipts)
GET /activity-logs                                      filters: action, user_id, target_type
GET /stats                                              item counts by type/status + active/overdue checkouts
```

### App admin (root domain)

```
GET /accounts                                           list all tenant accounts
```

---

## 5. Client Examples

### Python

```python
import requests

class KBM:
    def __init__(self, base, token):
        self.base = f"{base}/api/v1"
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"

    def get(self, path, **params):
        r = self.s.get(f"{self.base}{path}", params=params)
        r.raise_for_status()
        return r.json()

    def post(self, path, **body):
        r = self.s.post(f"{self.base}{path}", json=body)
        r.raise_for_status()
        return r.json()

kbm = KBM("https://acme.example.com", "kbm_1a2b3c4d_...")

# Everything overdue, for a daily Slack reminder
overdue = kbm.get("/checkouts", overdue=True)["checkouts"]
for c in overdue:
    print(f"{c['item']['label']} — {c['checked_out_to']} (due {c['expected_return_date'][:10]})")

# Check a key out to a contractor
result = kbm.post("/items/KA001/checkout",
                  copies=1, checked_out_to="Jane Contractor",
                  expected_return_date="2026-07-20")
print("Receipt/checkout id:", result["checkout"]["id"])
```

### JavaScript / Node

```javascript
const BASE = "https://acme.example.com/api/v1";
const HEADERS = {
  "Authorization": `Bearer ${process.env.KBM_TOKEN}`,
  "Content-Type": "application/json",
};

async function kbm(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, { headers: HEADERS, ...options });
  const body = await res.json();
  if (!res.ok) throw new Error(`${body.error.code}: ${body.error.message}`);
  return body;
}

// List available keys for a property
const { items } = await kbm("/items?type=Key&status=available&property_id=3");

// Create a property from your CRM
await kbm("/properties", {
  method: "POST",
  body: JSON.stringify({
    name: "Maple Apartments",
    address_line1: "12 Maple St",
    city: "Springfield",
    state: "IL",
  }),
});
```

### PowerShell

```powershell
$headers = @{ Authorization = "Bearer $env:KBM_TOKEN" }
$stats = Invoke-RestMethod "https://acme.example.com/api/v1/stats" -Headers $headers
$stats.items
```

---

## 6. Recipes

**Nightly overdue report** — `GET /checkouts?overdue=true&per_page=100`,
page through, notify.

**Sync properties from your CRM** — `GET /properties?q=<address>` to check
for an existing record, `POST /properties` when missing, `PATCH` when found.

**Key kiosk / scanner app** — scan the printed custom id, then
`GET /items/{scanned_id}` → show details → `POST .../checkout` or
`.../checkin`. Custom ids resolve directly in the URL.

**Dashboard widget** — `GET /stats` returns item counts by type/status plus
active and overdue checkout counts in one call.

**Deprovision an employee** — `PATCH /users/{id} {"is_active": false}`
blocks their web login *and* kills their API tokens at once.

---

## 7. Operational Notes

- **Audit trail**: every write through the API produces the same activity-log
  entries as the web UI (visible under Activity Logs, `via: api` in the
  metadata), attributed to the token's user.
- **Rate limits**: only token creation is rate-limited today. Be a good
  citizen anyway; batch where possible.
- **Notifications**: key checkouts/check-ins trigger the tenant's configured
  email notifications exactly like the web flows.
- **HTTPS**: production deployments sit behind TLS; never send a token over
  plain HTTP.
- **Request size**: bodies are capped (16 MB default, `MAX_CONTENT_LENGTH`).
