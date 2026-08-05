"""KBM MCP server — control your KBM account from Claude (or any MCP client).

A thin stdio MCP wrapper around the KBM REST API v1, so you can say things
like "add a key for 12 Maple St", "check lockbox LBA001 out to Agent Bob",
or "what's overdue?" and have the assistant do it.

Configuration (environment variables):
    KBM_BASE_URL   Your company's KBM URL, e.g. https://vesta.vkeys.app
    KBM_API_TOKEN  An API token created under Settings -> API Keys
                   (or POST /api/v1/auth/tokens). Format: kbm_xxxx_...

Run:  python kbm_mcp.py     (spoken by MCP clients over stdio)

Register with Claude Code:
    claude mcp add kbm --scope user \
      -e KBM_BASE_URL=https://<your-subdomain>.vkeys.app \
      -e KBM_API_TOKEN=kbm_... \
      -- python /path/to/kbm_mcp.py
"""

from __future__ import annotations

import os
from typing import Any

import requests

try:  # MCP SDK >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # MCP SDK 1.x
    from mcp.server.fastmcp import FastMCP as _Server

mcp = _Server("kbm")

_BASE = (os.environ.get("KBM_BASE_URL") or "").rstrip("/")
_TOKEN = os.environ.get("KBM_API_TOKEN") or ""


class KBMError(Exception):
    pass


def _call(method: str, path: str, params: dict | None = None,
          body: dict | None = None) -> Any:
    if not _BASE or not _TOKEN:
        raise KBMError(
            "KBM_BASE_URL and KBM_API_TOKEN must be set in the MCP server's "
            "environment. Create a token under Settings -> API Keys in KBM."
        )
    if params:
        params = {k: v for k, v in params.items() if v is not None}
    if body:
        body = {k: v for k, v in body.items() if v is not None}
    resp = requests.request(
        method,
        f"{_BASE}/api/v1{path}",
        params=params or None,
        json=body,
        headers={"Authorization": f"Bearer {_TOKEN}"},
        timeout=30,
    )
    try:
        payload = resp.json()
    except ValueError:
        resp.raise_for_status()
        raise KBMError(f"Unexpected non-JSON response ({resp.status_code})")
    if resp.status_code >= 400:
        err = (payload or {}).get("error", {})
        raise KBMError(f"{err.get('code', resp.status_code)}: "
                       f"{err.get('message', 'API error')}")
    return payload


# ---------------------------------------------------------------- overview

@mcp.tool()
def kbm_stats() -> dict:
    """Account overview: item counts by type/status plus active and overdue
    checkout counts. Good first call to orient yourself."""
    return _call("GET", "/stats")


@mcp.tool()
def whoami() -> dict:
    """Show which KBM user/account this connection is authenticated as."""
    return _call("GET", "/me")


# ------------------------------------------------------------------- items

@mcp.tool()
def list_items(item_type: str | None = None, status: str | None = None,
               q: str | None = None, property_id: int | None = None,
               assigned_to: str | None = None, page: int = 1,
               per_page: int = 25) -> dict:
    """List inventory items. item_type: Key | Lockbox | Sign. status e.g.
    available, checked_out, assigned. q searches id/label/address/location."""
    return _call("GET", "/items", params={
        "type": item_type, "status": status, "q": q,
        "property_id": property_id, "assigned_to": assigned_to,
        "page": page, "per_page": per_page,
    })


@mcp.tool()
def get_item(ref: str) -> dict:
    """Get one item (with its active checkouts) by numeric id or custom id
    like KA042 / LBA001 / SA003."""
    return _call("GET", f"/items/{ref}")


@mcp.tool()
def create_key(label: str, total_copies: int | None = None,
               property_id: int | None = None,
               property_unit_id: int | None = None,
               key_hook_number: str | None = None,
               keycode: str | None = None, location: str | None = None,
               address: str | None = None) -> dict:
    """Create a key. Label is the human name, e.g. 'Front Door - 12 Maple St'.
    Link it to a property with property_id (use list_properties to find it)."""
    return _call("POST", "/items", body={
        "type": "Key", "label": label, "total_copies": total_copies,
        "property_id": property_id, "property_unit_id": property_unit_id,
        "key_hook_number": key_hook_number, "keycode": keycode,
        "location": location, "address": address,
    })


@mcp.tool()
def create_lockbox(label: str, code_current: str | None = None,
                   supra_id: str | None = None,
                   property_id: int | None = None,
                   location: str | None = None,
                   address: str | None = None) -> dict:
    """Create a lockbox (optionally with its current code and Supra id)."""
    return _call("POST", "/items", body={
        "type": "Lockbox", "label": label, "code_current": code_current,
        "supra_id": supra_id, "property_id": property_id,
        "location": location, "address": address,
    })


@mcp.tool()
def create_sign(label: str, sign_subtype: str | None = None,
                piece_type: str | None = None, rider_text: str | None = None,
                material: str | None = None, condition: str | None = None,
                property_id: int | None = None,
                location: str | None = None) -> dict:
    """Create a sign. sign_subtype: 'Piece' or 'Assembled Unit'."""
    return _call("POST", "/items", body={
        "type": "Sign", "label": label, "sign_subtype": sign_subtype,
        "piece_type": piece_type, "rider_text": rider_text,
        "material": material, "condition": condition,
        "property_id": property_id, "location": location,
    })


@mcp.tool()
def update_item(ref: str, fields: dict) -> dict:
    """Update an item's descriptive fields (label, location, address, plus
    type-specific fields like total_copies, code_current, rider_text...).
    Status cannot be set here — use checkout/checkin/assign instead."""
    return _call("PATCH", f"/items/{ref}", body=fields)


@mcp.tool()
def checkout_item(ref: str, checked_out_to: str | None = None,
                  copies: int | None = None, purpose: str | None = None,
                  expected_return_date: str | None = None,
                  contact_id: int | None = None, code: str | None = None,
                  assigned_to: str | None = None,
                  address: str | None = None) -> dict:
    """Check an item out. Keys: pass copies/checked_out_to/purpose/
    expected_return_date (YYYY-MM-DD) and optionally contact_id (links the
    loan + enables email notification). Lockboxes: pass the CURRENT code
    (required) and assigned_to/address."""
    return _call("POST", f"/items/{ref}/checkout", body={
        "checked_out_to": checked_out_to, "copies": copies,
        "purpose": purpose, "expected_return_date": expected_return_date,
        "contact_id": contact_id, "code": code,
        "assigned_to": assigned_to, "address": address,
    })


@mcp.tool()
def checkin_item(ref: str, checkout_id: int | None = None,
                 copies: int | None = None, code: str | None = None) -> dict:
    """Check an item back in. Keys: optionally target a specific loan with
    checkout_id (from get_item's active_checkouts). Lockboxes: pass the
    current code — it rotates on check-in."""
    return _call("POST", f"/items/{ref}/checkin", body={
        "checkout_id": checkout_id, "copies": copies, "code": code,
    })


@mcp.tool()
def assign_item(ref: str, assignment_type: str | None = None,
                assigned_to: str | None = None,
                property_id: int | None = None,
                property_unit_id: int | None = None,
                copies: int | None = None,
                expected_return_date: str | None = None) -> dict:
    """Long-term assignment (vs. a checkout). Keys need assignment_type:
    tenant | contractor | property. contractor requires expected_return_date;
    property requires property_id."""
    return _call("POST", f"/items/{ref}/assign", body={
        "assignment_type": assignment_type, "assigned_to": assigned_to,
        "property_id": property_id, "property_unit_id": property_unit_id,
        "copies": copies, "expected_return_date": expected_return_date,
    })


# --------------------------------------------------------------- checkouts

@mcp.tool()
def list_checkouts(active: bool | None = None, overdue: bool | None = None,
                   item_id: int | None = None, contact_id: int | None = None,
                   person: str | None = None, page: int = 1,
                   per_page: int = 25) -> dict:
    """Checkout history. overdue=True gives active loans past their expected
    return date — the go-to for 'what's overdue?'."""
    return _call("GET", "/checkouts", params={
        "active": active, "overdue": overdue, "item_id": item_id,
        "contact_id": contact_id, "person": person,
        "page": page, "per_page": per_page,
    })


# -------------------------------------------------------------- properties

@mcp.tool()
def list_properties(q: str | None = None, page: int = 1,
                    per_page: int = 25) -> dict:
    """List/search properties. q matches name, address, and city — use this
    to resolve 'the Maple St property' to a property_id."""
    return _call("GET", "/properties", params={"q": q, "page": page,
                                               "per_page": per_page})


@mcp.tool()
def get_property(property_id: int) -> dict:
    """Property detail including its units and item counts."""
    return _call("GET", f"/properties/{property_id}")


@mcp.tool()
def create_property(name: str, address_line1: str,
                    address_line2: str | None = None,
                    city: str | None = None, state: str | None = None,
                    postal_code: str | None = None,
                    property_type: str | None = None,
                    notes: str | None = None) -> dict:
    """Create a property. name and address_line1 are required."""
    return _call("POST", "/properties", body={
        "name": name, "address_line1": address_line1,
        "address_line2": address_line2, "city": city, "state": state,
        "postal_code": postal_code, "type": property_type, "notes": notes,
    })


# ---------------------------------------------------------------- contacts

@mcp.tool()
def list_contacts(q: str | None = None, contact_type: str | None = None,
                  page: int = 1, per_page: int = 25) -> dict:
    """List/search contacts (q matches name, company, email, phone)."""
    return _call("GET", "/contacts", params={"q": q, "type": contact_type,
                                             "page": page,
                                             "per_page": per_page})


@mcp.tool()
def create_contact(name: str, email: str | None = None,
                   phone: str | None = None, company: str | None = None,
                   contact_type: str | None = None,
                   notes: str | None = None) -> dict:
    """Create a contact. Link contacts to key checkouts (contact_id) to power
    email notifications and history."""
    return _call("POST", "/contacts", body={
        "name": name, "email": email, "phone": phone, "company": company,
        "contact_type": contact_type, "notes": notes,
    })


# ------------------------------------------------------------- smart locks

@mcp.tool()
def list_smart_locks(q: str | None = None, property_id: int | None = None,
                     page: int = 1, per_page: int = 25) -> dict:
    """List/search smart locks."""
    return _call("GET", "/smart-locks", params={"q": q,
                                                "property_id": property_id,
                                                "page": page,
                                                "per_page": per_page})


@mcp.tool()
def create_smart_lock(label: str, code: str, property_id: int | None = None,
                      provider: str | None = None,
                      backup_code: str | None = None,
                      instructions: str | None = None,
                      notes: str | None = None) -> dict:
    """Create a smart lock. label and code are required."""
    return _call("POST", "/smart-locks", body={
        "label": label, "code": code, "property_id": property_id,
        "provider": provider, "backup_code": backup_code,
        "instructions": instructions, "notes": notes,
    })


if __name__ == "__main__":
    mcp.run()
