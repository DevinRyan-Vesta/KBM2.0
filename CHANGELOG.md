# Changelog

All notable changes to KBM (Keybox Manager) are documented here.
Versioning: MAJOR.MINOR.PATCH. The running version is shown in the app
sidebar and defined as `APP_VERSION` in `config.py`.

## [2.5.0] — 2026-10-27

Quality pass: VKeys now shares the Vesta OS design system so the two apps
read as one family, and the rough edges of the web UI (native dialogs,
unstyled pages, duplicated page CSS) are gone.

### Changed
- **Design system** moved out of the base template into `static/css/app.css`
  with the Vesta OS tokens: light-first `#f5f6f8` page on white cards, one
  brand red (`#d92632`) for primary actions and active marks, blue text
  actions, Inter/Segoe type at 15px, 12px card radius, roomy tables with no
  zebra striping, pill status badges using the shared ok/info/warn/bad/purple
  tone pairs, and the matching dark palette. Every old `--color-*` variable
  is aliased, so page-level styles keep working.
- **Shell**: 236px white rail with the key-mark logo, section labels, active
  item marked with a red icon, and a user card (initials avatar, name, role)
  with help / API keys / profile / theme icon buttons and a Sign out button
  in the rail footer. Sticky white toolbar with a centred search pill
  (`Ctrl K` or `/` focuses it) and a help icon for the current page. On
  phones the rail is an off-canvas drawer with a backdrop that closes on
  navigation; modals become bottom sheets; targets grow to 44px.
- **Theme** is `data-theme` on `<html>` (persisted as `vkeys-theme`,
  migrating the old `kbm-theme` key) with a sun/moon toggle. `body.light` /
  `body.dark` stay in sync for existing overrides.
- **Dialogs**: every native `confirm()` / `prompt()` / `alert()` is gone.
  Destructive forms carry `data-confirm` and open a confirm sheet (title,
  what-it-does box, red confirm button, Esc/Enter, focus trap); bulk
  status / assign use the same sheet with a select or text field;
  validation messages are toasts. `confirmAction()` and `undoToast()` are
  available to every page.
- **Toasts** are bottom-centre white cards with Lucide icons and a dismiss
  button; flash messages get an icon and the same tone colours.
- **Tables** on every list page sort client-side by clicking a header
  (`<table data-sortable>`); toolbar buttons (Filters, Export, Import, Add)
  carry icons.
- **Sign-in, sign-up and the app-admin dashboard** were written against
  Tailwind classes that were never loaded and rendered unstyled; they now
  use the design system (360px sign-in card, grouped sign-up form, summary
  strip + sortable accounts table).
- **Help Center** topic icons are Lucide glyphs instead of emoji.
- One brand red everywhere: app, landing page, favicon and notification
  emails (`#d92632`); the email header no longer says "VKeys 2.0".
- Shared CSS (bulk bar, export menu, autocomplete, copy badges, lockbox code
  chips, dashboard stat strip, report tabs) lives in `app.css` instead of
  being repeated in each page.

### Added
- Export (CSV / Excel) on the Properties page.
- A shared export menu (`showExportMenu(event, type, formats)`) any page can
  use.

### Security
- Pillow 12.3.0 → 13.0.0, closing the 41 open Dependabot alerts against it.
  Pillow is only used for QR label rendering and smart-lock photo
  validation; both are covered by the smoke suite.
- Werkzeug 3.1.6 → 3.1.9 (`safe_join()` accepted Windows special device
  names, GHSA-g6x2-hccm-hh4m).

### Fixed
- Contacts empty state no longer links to a non-existent import page.
- The smoke tests resolve record ids from the labels they create instead of
  hard-coding `1` / `2`, so the suite passes regardless of test order (the
  upcoming-returns export test failed whenever the API tests ran first).

## [2.4.0] — 2026-08-05

Domain migration release: the platform now lives at **vkeys.app** (vkeys.io
and the legacy buywithvesta.com redirect there).

### Added
- **Public landing page** on the apex domain: standalone marketing page
  (light/dark aware) describing the product, with an email capture form
  ("notify me when the app goes live"). Subscribers are stored in the
  master DB; app admins can view/export them at Admin → Subscribers.
- **Admin subdomain**: the app-admin interface now lives on
  `admin.<BASE_DOMAIN>`. The apex serves only the public site; old
  `/admin/*` and `/auth/login` bookmarks on the apex 301 to the admin host.
- **www redirect**: `www.<BASE_DOMAIN>` now 301s to the apex (previously it
  404'd as an unknown tenant).
- **Expanded reserved subdomains**: ~120 infra/service names (smtp, mx,
  ns1, status, billing, secure, …) can no longer be registered as tenant
  subdomains.
- **MCP server** (`mcp_server/`): control KBM from Claude or any MCP client
  ("add a key for 12 Maple St", "what's overdue?") via the REST API.
- Favicon (SVG key mark) served on all pages.
- Multi-domain external-Traefik override (`compose.external-traefik.yaml`):
  vkeys.app platform + tenant routers, vkeys.io and buywithvesta.com
  HTTPS redirects, Hostinger DNS-01 wildcard resolver support.

## [2.3.0] — 2026-07-13

### Added
- **API Keys management page** (`/settings/api-keys`, linked from the
  sidebar): create keys with a name and optional expiry (30/90/365 days or
  never), copy the key from a show-once reveal box, and revoke keys with
  one click. Every logged-in user manages their own keys; admins see all
  keys in the account with owner and last-used time. Key creation and
  revocation are recorded in the tenant activity log.
- Sidebar links: "API Keys" in the Administration section (admins) and in
  the sidebar footer (all users). The in-app "? Help" button on the page
  opens the API help topic, updated to describe the new UI.
- Tests for the page (`tests/test_api_keys_ui.py`): show-once behavior,
  UI-minted keys authenticating against the API, revocation, and
  cross-user permission checks.

## [2.2.0] — 2026-07-13

Full REST API release.

### Added
- **REST API v1** at `/api/v1` covering the whole app: items (lockboxes,
  keys, signs) with checkout / check-in / assign actions that mirror the web
  flows exactly, checkout history, properties + units, contacts, smart
  locks, audits (read), users, tenant settings, activity logs, and an
  inventory stats summary. App admins get a cross-tenant `/api/v1/accounts`
  endpoint on the root domain.
- **API tokens**: `POST /api/v1/auth/tokens` exchanges a login email + PIN
  for a long-lived Bearer token (rate-limited; optional expiry; stored
  hashed in the master DB, shown once). Tokens inherit the user's role;
  list/revoke endpoints included. New `api_tokens` table is created
  automatically on boot.
- **API reference docs** at `/api/v1/docs` (interactive, self-contained)
  plus a machine-readable OpenAPI 3.0 spec at `/api/v1/openapi.json`.
- **API integration guide** (`API_DOCUMENTATION.md`) for external apps:
  auth walkthrough, conventions, per-resource examples in curl / Python /
  JavaScript / PowerShell, and common integration recipes.
- **"API & Integrations" Help Center topic** so admins can discover the
  API and token management from inside the app.
- **API test suite** (`tests/test_api.py`, 20 tests) exercising the token
  lifecycle, every resource family, role gating, and tenant isolation.
- All API writes create the same activity-log entries as the web UI, and
  key checkouts/check-ins trigger the same email notifications.
- JSON error responses (`{"error": {"code", "message"}}`) for every `/api/`
  path, including 404/405/429 raised outside the blueprint.

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
