# Changelog

All notable changes to KBM (Keybox Manager) are documented here.
Versioning: MAJOR.MINOR.PATCH. The running version is shown in the app
sidebar and defined as `APP_VERSION` in `config.py`.

## [2.1.0] — 2026-07-02

Deployment-readiness release: built-in Help Center, a round of bug fixes
found in a full-codebase audit, security hardening, and repo cleanup.

### Added
- **Built-in Help Center** at `/help` with 15 illustrated guides covering
  every feature (lockboxes, keys, signs, check in/out, receipts, audits,
  reports, properties, contacts, smart locks, imports, search, users & roles,
  settings, getting started).
- **Context-sensitive "? Help" button** in the top bar of every page — opens
  the guide for the page you're on.
- **Tooltips** across the app: hover hints on toolbar buttons (Export,
  Import, Filters, Add …) and `?` markers on complex form fields (key hook
  number, key code, total copies, master key, lockbox codes, Supra ID,
  sign/rider types).
- **Real end-to-end test suite** (`tests/`) that boots the production
  multi-tenant app, provisions a tenant, and exercises every page plus the
  core workflows (create → checkout → receipt → check-in → audit → export).
- **App version** (`APP_VERSION` in `config.py`) displayed in the sidebar.
- **Demo account seeder** (`create_demo_account.py`) — provisions a "Demo
  Realty Group" tenant with realistic sample data for testing.
- **Favicon** (red key mark, SVG).
- **Keyboard shortcut**: press `/` anywhere to focus the global search.
- **CI workflow**: GitHub Actions runs the test suite on every pull request.
- `ToDo.txt` reorganized into a live roadmap (stale entries verified and
  closed; new improvement ideas added).
- This changelog.

### Fixed
- **Overdue Returns and Upcoming Returns exports crashed** (HTTP 500,
  `date`/`datetime` arithmetic error) whenever the report had any rows.
- **Lockbox inventory export was always rejected** ("Invalid item type") due
  to a string-handling bug (`'lockboxes'.rstrip('s')` → `'lockboxe'`).
- **Export buttons on the Signs page were dead** (they called a JavaScript
  function that no longer exists); Properties and Contacts pages carried the
  same dead export code with no button at all. Signs now downloads directly
  like Keys/Lockboxes; the dead code is removed.
- **All five "Export ▾" buttons on the Reports page were dead** — the
  dropdown toggle function was never defined. Implemented.
- **"Last action by" was never recorded** when editing lockboxes, keys, or
  signs (the model wrote to a nonexistent attribute; the audit trail silently
  stayed empty for edits).
- **The public landing page was unreachable** — visiting the root domain
  redirected to a login form instead of the signup/landing page, because two
  routes both claimed `/` and the wrong one won.
- **Check In/Out APIs returned raw 500 errors on the root domain** (missing
  tenant guard).
- **Empty exports returned a bare "No data to export" error page**; they now
  flash a friendly note and return you to where you were.
- Several templates rendered whole export menus/scripts inside the page
  `<title>` tag (invalid HTML, duplicate element IDs); cleaned up on the
  Keys, Signs, Properties, and Contacts pages.

### Security
- **Login is now rate-limited** (10/minute, 50/hour per IP). The previous
  "rate limiting" wrapper was a no-op and was never even applied.
- **Session cookies are hardened**: `HttpOnly` (default on), `SameSite=Lax`,
  and `Secure` honored from the environment — these settings existed in the
  production templates but were never actually read by the app.
- **Upload size cap enforced** (`MAX_CONTENT_LENGTH`, default 16 MB) —
  previously unlimited despite being documented.
- **Production refuses to boot without a real `SECRET_KEY`** instead of
  silently falling back to a hard-coded value. Rotate any previously
  deployed key: old ones were committed to git history and must be treated
  as compromised.
- **The container now defaults to `ENV=production`** — a missing `.env`
  can no longer boot the container in DEBUG mode.
- **Cross-tenant defense in depth**: a logged-in user of one company is now
  explicitly blocked from another company's subdomain even if cookie scoping
  ever changes.
- **Permission consistency**: Owners can now do everything Admins can in
  inventory (edit/delete) and unit deletion; deleting inventory items now
  requires admin/owner (previously any non-agent user could delete).
- Tenant database sessions are now properly scoped per request instead of
  one shared session per tenant (thread-safety / state-bleed risk under
  concurrent use).

### Removed / cleaned up
- Legacy single-tenant app (`app.py`, `auth/views.py`, `auth/models.py`,
  `create_admin.py`) and its orphaned templates (`login.html`, `users.html`,
  `user_form.html`, `lockboxes_list.html`) — the deployed app has been
  `app_multitenant.py` for a long time, and the legacy app exposed an
  unauthenticated debug admin-creation endpoint if ever run by mistake.
- Committed build junk: `__pycache__` bytecode, `.bak` files, a stray log
  file, one-off migration scripts (`add_filters_bulk_ops.py`,
  `fix_filter_bulk_issues.py`), and stale docs (`Documentation`,
  `CLEANUP_SUMMARY.md`).
- Old test files that targeted the removed single-tenant app.

## [2.0.0] — 2025-11 → 2026-06 (pre-changelog history)

Highlights reconstructed from the git log, newest first:

- Traefik reverse-proxy support with DNS-01 wildcard TLS (Cloudflare), as an
  alternative to Caddy.
- Import wizard overhaul: review step with fuzzy property matching,
  duplicate handling, and on-the-fly property creation.
- Lockbox list fixes (row action buttons, script ordering) and a simplified
  Add Lockbox form (property assignment moved to the detail page).
- Self-service system updater for app admins (git-based, Docker-driven)
  with self-healing for permissions and auto-stash.
- Session idle timeout with client-side warning; CSRF token lifetime tied
  to the session.
- Per-tenant settings (email notification switches, overdue grace period,
  low-keys threshold, default checkout duration, receipt header/footer).
- Email notifications: checkout/check-in confirmations and overdue
  reminders, with spam-prevention fixes.
- Smart locks module: codes, property/unit links, and validated photo
  uploads.
- Global search with autocomplete across all record types.
- Audits module: key box audits with print sheets, result input, apply
  corrections; low-copy report; key box reorganization tool.
- Sign builder: assemble sign pieces (frames, signs, riders) into units.
- Reports page (overdue, upcoming, long-term, low keys, checked-out keys,
  property assignments) with CSV/Excel/PDF exports.
- Multi-tenant architecture: master database + per-tenant SQLite databases,
  subdomain routing, tenant signup, and app-admin console.
- Original single-tenant KBM 2.0: lockboxes, keys, signs, checkouts,
  receipts, properties, contacts, PIN-based auth.
