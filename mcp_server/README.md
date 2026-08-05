# KBM MCP Server

Control your KBM account from Claude (Claude Code, Claude Desktop, or any
MCP client): *"add a key for 12 Maple St"*, *"check lockbox LBA001 out to
Agent Bob"*, *"what's overdue?"*.

This is a thin stdio wrapper around the [KBM REST API v1](../API_DOCUMENTATION.md) —
every action goes through the same audited, token-authenticated API as any
other integration, attributed to the user who created the token.

## Setup

1. **Create an API token** in KBM: log in on your company subdomain →
   **Settings → API Keys → Create key**. Copy the `kbm_…` token (shown once).

2. **Install dependencies** (Python 3.10+):

   ```bash
   pip install -r mcp_server/requirements.txt
   ```

3. **Register with Claude Code:**

   ```bash
   claude mcp add kbm --scope user -e KBM_BASE_URL=https://YOURCOMPANY.vkeys.app -e KBM_API_TOKEN=kbm_YOUR_TOKEN -- python C:/path/to/KBM2.0/mcp_server/kbm_mcp.py
   ```

   Or for **Claude Desktop**, add to `claude_desktop_config.json`:

   ```json
   {
     "mcpServers": {
       "kbm": {
         "command": "python",
         "args": ["C:/path/to/KBM2.0/mcp_server/kbm_mcp.py"],
         "env": {
           "KBM_BASE_URL": "https://YOURCOMPANY.vkeys.app",
           "KBM_API_TOKEN": "kbm_YOUR_TOKEN"
         }
       }
     }
   }
   ```

## What it can do

| Area | Tools |
|------|-------|
| Overview | `kbm_stats`, `whoami` |
| Items | `list_items`, `get_item`, `create_key`, `create_lockbox`, `create_sign`, `update_item` |
| Actions | `checkout_item`, `checkin_item`, `assign_item` |
| History | `list_checkouts` (incl. `overdue=True`) |
| Properties | `list_properties`, `get_property`, `create_property` |
| Contacts | `list_contacts`, `create_contact` |
| Smart locks | `list_smart_locks`, `create_smart_lock` |

Item references accept either the numeric id or the printed custom id
(`KA042`, `LBA001`, `SA003`).

## Notes

- The token inherits the role of the user who created it — admin tokens can
  do admin things, regular tokens can't.
- Deletes are intentionally not exposed as MCP tools; do those in the web UI.
- Every write shows up in KBM's Activity Logs with `via: api`.
