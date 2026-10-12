# Launch Checklist for a New Project
---

Use this checklist after copying MysticAuth into a real application. A
**downstream project** is the new application created from this template. The
template provides reusable code and a working development environment; this
checklist covers decisions that only the new application's owner can make.

Terms used here: **SMTP** is the standard protocol used to send email;
**OAuth** lets a user sign in with another provider such as Google;
**TLS** is the encryption used by HTTPS; a **VPS** is a rented virtual server;
and an **off-host backup** is a backup stored somewhere other than the server
that runs the application.

Read [Using This Repository as a Template](overview.md) first if you have not
chosen an ownership split yet. Work through the sections that apply to the
features and deployment mode you will actually use.

## 1. Create and customize the project

- Run the [Quickstart](quickstart.md) and confirm the dev stack, migrations,
  worker, frontend, and Bugsink start successfully.
- Keep application code in the `app/` trees and treat `mystic_auth/` as
  upstream-owned. Use the [ownership split](ownership-split.md) and the
  [upstream sync guide](syncing-upstream/README.md).
- Set the application name, brand color, favicon/logo, support address,
  language choices, landing page, and application-owned routes.
- Add application resources, migrations, policies, permissions, and tests
  using [Building On This Template](customization.md).
- Decide whether the project uses password signup, Google OAuth, or both. Do
  not enable a sign-in option in the UI until its real provider settings have
  been configured and tested.

## 2. Complete the product and legal review

- Replace the Terms and Privacy page operator placeholders with the real legal
  entity, contact address, jurisdiction, age threshold, retention rules, legal
  bases, and enabled providers.
- Review the documents against the actual project: collected data, session
  geolocation, SMTP provider, OAuth, Bugsink, cookies, audit retention, and
  any application-specific data.
- Have qualified counsel review the final text for each jurisdiction in which
  the service operates.
- After branding and copy settle, add screenshot-based visual regression for
  the customized legal pages, signup flow, and other high-value public pages.

## 3. Configure real integrations

- Configure a real SMTP provider and test signup verification, resend,
  password reset, and account-deletion confirmation where applicable.
- Decide how delivery failures, retries, bounces, and abuse will be noticed;
  the template's worker logs and Bugsink error reporting are not a complete
  email-delivery monitoring service.
- Configure Google OAuth redirect URLs and credentials if OAuth is enabled.
  The template requests only `openid email profile`, Google's basic identity
  scopes. That normally avoids the sensitive/restricted-scope review path, but
  Google can still require brand or policy steps for a public app. Check the
  current Google requirements before launch.
- Configure Bugsink and confirm both backend and frontend errors arrive in the
  intended project without exposing sensitive request data.
- Keep `EMAIL_ENABLED=false` in local and automated test environments.

### Google OAuth: setup, testing, and verification

1. In Google Cloud Console, create separate projects for development and
   production. Configure the OAuth consent screen, application name, support
   email, home page, privacy-policy URL, and authorized domain information.
2. Choose **Internal** only when every user belongs to the same Google
   Workspace or Cloud Identity organization. Choose **External** for a public
   application or one that accepts ordinary Google accounts.
3. While an External app is in **Testing**, add every tester to the test-user
   list. Testing limits access and can cause test authorizations to expire.
4. For production, publish the External app and follow Google's verification
   process if the app requests sensitive or restricted scopes, or if Google
   requires brand verification for the configured public identity. Verification
   is a Google review of the app identity, consent-screen information, privacy
   policy, requested scopes, and sometimes the live user journey. It is not a
   MysticAuth code setting.
5. Create a Web application OAuth client. Add the exact production callback
   URL from `GOOGLE_REDIRECT_URI`, including `https`, hostname, path, and
   trailing slash. Never put the client secret in frontend code.
6. Test a new Google account and an existing password account. Confirm
   cancelled consent, unverified email handling, logout, and the callback
   through the real domain.

Google's official guidance is in [OAuth app state
overview](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview),
[OAuth policies](https://developers.google.com/identity/protocols/oauth2/policies),
and [verification requirements](https://support.google.com/cloud/answer/13464321).
Provider rules can change, so treat those pages as the authority at launch.

### Email provider choices

Gmail SMTP is acceptable for a small, low-volume deployment when the sending
Google account has 2-Step Verification enabled and uses an App Password. The
App Password is a provider credential, not the normal Google account password.
Expect provider sending limits and less operational visibility than a
transactional email service.

For a larger or user-facing service, a transactional provider is usually the
better operational choice. The built-in sender currently uses `FROM_EMAIL` as
the SMTP username and `GMAIL_APP_PASSWORD` as the SMTP password, while
`SMTP_HOST` and `SMTP_PORT` select the server. A provider with different
authentication or an API-only integration needs a small email-sender adapter;
do not merely rename a provider password and assume the existing code matches
its authentication rules. For any provider, configure domain authentication
and bounce/complaint notifications where available. Do not run an
internet-facing mail server on the same VPS unless mail operations are a
deliberate part of the project. See [Backend Settings](../environment/backend.md)
for the exact settings the template currently supports.

## 4. Prepare a VPS deployment

- Use the production environment file and run `check-env` before startup.
- Generate distinct production secrets; never reuse development values.
- Set the real domain, frontend/backend URLs, trusted proxy settings, SMTP,
  OAuth, Bugsink, and any GeoIP configuration.
- Use the production Compose mode with Caddy-managed TLS and verify cookie,
  CORS, redirect, and proxy behavior through the real domain.
- Point DNS records at the VPS and allow inbound TCP ports 80 and 443 so Caddy
  can obtain and renew the HTTPS certificate. If another provider terminates
  TLS, follow that provider's certificate, forwarding, and client-IP guidance
  instead of enabling a second TLS terminator.
- Create the first system user through the documented bootstrap command.
- Test migrations against a production-like database copy before applying
  them to the live database.

## 5. Make recovery and operations real

- Create a Backblaze B2 bucket and a bucket-scoped application key, then set
  `B2_BUCKET`, `RCLONE_CONFIG_B2_ACCOUNT`, `RCLONE_CONFIG_B2_KEY`, and
  `BACKUP_UPLOAD_COMMAND` as documented in [Migrations and Backups](../deployment/migrations-and-backups.md#backblaze-b2-off-host-copies).
  Local `./backups` files alone do not protect against host or disk loss.
- Run `make restore-drill`, confirm a dump appears in B2, download that exact
  object, and restore it into a disposable database. Confirm dump, verification,
  and upload failures appear in Bugsink.
- Keep the required environment secrets recoverable in a password manager or
  other protected operator system; a database dump alone cannot restore the
  application.
- Add host or external monitoring for uptime, disk space, container health,
  TLS expiry, and backup freshness. Bugsink receives backup dump, verification,
  and upload failures, but it does not replace checking that recent B2 objects
  exist.
- Decide whether periodic full dumps meet the project's recovery-point needs.
  **PITR** (point-in-time recovery) means restoring a database to a selected
  time using continuous write-ahead-log archiving. If losing up to one backup
  interval of writes is unacceptable, use managed Postgres or a WAL/PITR tool
  instead.
- Document who handles incidents, credential rotation, restores, provider
  outages, and account-abuse reports.

## 6. Perform the final acceptance pass

- Run the full GitHub CI pipeline on the downstream repository.
- Run the opt-in live-deployment smoke test against the actual domain.
- Test email, OAuth, login lockout, password reset, logout-all, account
  deletion, backups, restore, and worker execution end to end.
- Manually test keyboard-only navigation, focus management, dialogs, and a
  representative screen-reader flow; automated axe scans do not cover all of
  these behaviors.
- Record the deployment mode, image versions, migration head, backup schedule,
  restore procedure, monitoring destinations, and rollback plan.

The reusable MysticAuth template does not need all of these values filled in.
They become required when a downstream project is customized and prepared for
real users. The template's current backup limitations and deliberate scope
boundaries are recorded in [Known Concerns](../concerns/README.md).

---
