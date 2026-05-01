# Email notifications setup

KBM 2.0 sends transactional emails when items are checked out, checked in,
and when items become overdue. All sending goes through generic SMTP, so any
provider works.

When `SMTP_HOST` is empty, email is silently skipped — the rest of the app
keeps working. So you can deploy without configuring email and add it later.

---

## Recommended provider: Resend

Free up to 100 emails/day, no credit card required. Best deliverability for
a small project.

1. Sign up at <https://resend.com>.
2. **Add and verify your domain** (`buywithvesta.com`):
   - Domains → Add Domain → enter `buywithvesta.com`.
   - Resend gives you a few DNS records (SPF, DKIM, optionally DMARC). Add
     them at your DNS provider (Cloudflare, Hostinger DNS — wherever your
     records live now).
   - Wait a few minutes, click Verify. You can use the sandbox sender
     (`onboarding@resend.dev`) to test before this is verified, but it can
     only deliver to the email you signed up with.
3. Create an API key: API Keys → Create API Key → "Send access" only.
   Copy the value (starts with `re_…`) — you can't see it again.
4. On the VPS, edit `/opt/kbm/.env`:
   ```
   SMTP_HOST=smtp.resend.com
   SMTP_PORT=465
   SMTP_USE_SSL=true
   SMTP_USE_STARTTLS=false
   SMTP_USERNAME=resend
   SMTP_PASSWORD=re_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   SMTP_FROM=notifications@buywithvesta.com
   SMTP_FROM_NAME=Vesta KBM
   ```
5. Restart the app. Either via the in-app updater (App Admin → System
   Updates → Restart Containers) or:
   ```bash
   docker compose restart python-app
   ```

That's it. The app picks up the env on next start.

### Other providers

The app uses only stdlib `smtplib`, so anything that speaks SMTP works. A
few alternatives:

| Provider | Host | Port | Notes |
|---|---|---|---|
| **Resend** | `smtp.resend.com` | 465 SSL | Recommended. Free 100/day. |
| **Brevo** (Sendinblue) | `smtp-relay.brevo.com` | 587 STARTTLS | Free 300/day. |
| **Hostinger Mail** | `smtp.hostinger.com` | 465 SSL | Comes with hosting; deliverability is hit-and-miss for app-sent mail. |
| **Gmail / Workspace** | `smtp.gmail.com` | 587 STARTTLS | Needs an "app password". 500/day soft cap. Not recommended for transactional. |

For STARTTLS providers, set:
```
SMTP_USE_SSL=false
SMTP_USE_STARTTLS=true
```

---

## How recipient lookup works

When an item is checked out / assigned / checked in, the recipient is stored
as a free-text name (e.g. `Tracy Smith`). To find that person's email, the
app does a case-insensitive lookup against the **Contacts** table for the
current tenant: `Contact.name ILIKE '<name>'`.

- If a Contact exists with that exact name and has an email → email sent.
- If no Contact exists, or no email on file → silently skipped (no error).

So: to get email working for a tenant, **make sure the people you check items
out to are in Contacts with their email filled in**.

A future enhancement could let you pick a Contact directly during checkout
(rather than typing a name), eliminating the fuzzy-match step.

---

## Overdue reminders (daily cron)

The app does not poll for overdue items on its own. Wire the included script
to host cron for a daily run.

On the VPS:

```bash
crontab -e
```

Add:

```
# Send overdue-item reminders every day at 9am UTC
0 9 * * *  cd /opt/kbm && /usr/bin/docker compose exec -T python-app python -m utilities.send_overdue_reminders >> /opt/kbm/logs/overdue.log 2>&1
```

Notes:
- `-T` disables TTY allocation (cron has no terminal).
- The script logs how many tenants and overdue items it processed and how
  many emails it sent.
- It currently sends a reminder for **every** still-overdue active checkout
  on each run, so make sure the cron runs at most once per day.
- Items get reminded once per day until returned. If you want to throttle
  per-checkout (e.g. "only first day, then weekly"), we'd add a
  `last_overdue_reminder_sent_at` column on `ItemCheckout`. Punt for MVP.

To test the script manually before adding the cron entry:

```bash
docker compose exec python-app python -m utilities.send_overdue_reminders
```

It'll print to the terminal and only send if there are real overdue items
with matching contacts.

---

## Limitations / known scope

- **Lockboxes are not emailed.** The lockbox checkout flow doesn't create
  an `ItemCheckout` record — it just toggles `Item.status`. So there's no
  receipt to reference and no clean recipient field to use. Adding
  notifications for lockboxes would require either creating `ItemCheckout`
  rows for them too, or building a lockbox-specific notification path.
- **Sends are inline.** The HTTP request waits for SMTP. Resend usually
  returns in 200–500ms; if your provider is slow, the user sees a longer
  redirect. Adding a background queue (Celery/RQ) is the right fix when
  volume justifies it.
- **No retry on failure.** A failed send is logged and dropped.
- **No per-tenant on/off toggle yet.** Email is on globally as long as
  `SMTP_HOST` is set. Easy to add per-tenant later by adding a flag to
  `Account`.

---

## Troubleshooting

- **No email arrives, no error in logs**: check `docker compose logs python-app`
  for "Email skipped (SMTP not configured)" or "Email skipped (no recipients)".
  The latter usually means the contact name on the checkout doesn't match a
  Contact with an email.
- **"Authentication failed"**: API key wrong, or `SMTP_USERNAME` doesn't
  match what the provider wants. Resend's SMTP username is literally `resend`.
- **"Cert verify failed"**: rare. Means the provider's TLS cert isn't
  trusted by the python-app container. Try `SMTP_USE_STARTTLS=true SMTP_PORT=587`
  instead of port 465 SSL.
- **Email lands in spam**: add SPF + DKIM + DMARC records for your sending
  domain. Resend shows you exactly what to add. This matters a lot.
