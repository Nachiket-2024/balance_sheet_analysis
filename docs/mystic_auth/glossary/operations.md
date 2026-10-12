# Glossary: Operations
---

Error monitoring, geolocation, and localization terms. See [Glossary](README.md) for the full index.

---

## MaxMind GeoLite2

A free-to-download IP-to-city/country lookup database. This app uses a local `.mmdb` file from it to add best-effort location data to the Manage Sessions list; it's optional and off by default, and MaxMind's license means the file itself is never shipped in this repo. See [Session Geolocation](../geolocation/overview.md).

---

## geoipupdate

An optional container (off by default, enabled via the `geoip` Compose profile) that periodically re-downloads a fresh copy of the MaxMind GeoLite2-City database, so session geolocation stays accurate as MaxMind updates it over time. See [Docker Overview: Services](../docker/overview.md#services).

---

## Sentry SDK protocol / Bugsink

An error-reporting wire protocol originally built by Sentry, now also spoken by other tools including Bugsink, which this app self-hosts by default to catch unhandled backend exceptions and frontend crashes. Self-hosting keeps error payloads (which can contain emails or other personal data) on your own infrastructure instead of a third-party service. See [Error Monitoring](../error-monitoring/overview.md).

---

## PII

Short for Personally Identifiable Information: data that could identify a specific person, such as an email address or IP address. Error monitoring payloads can carry PII (in stack traces or request context), which is one of the reasons this app self-hosts Bugsink rather than defaulting to a third-party SaaS. See [Error Monitoring: Why Bugsink](../error-monitoring/overview.md#why-bugsink).

---

## i18n

Short for internationalization: the app's support for multiple display languages (English, Hindi, Marathi, Gujarati), including translated UI text and translated backend error codes. See [Translations Overview](../translations/overview/README.md).

---

## error code translation

The mechanism by which a stable, machine-readable error identifier from the backend (e.g. `INVALID_CREDENTIALS`) gets turned into a human-readable, localized message on the frontend, via a per-language `errors.json` lookup. See [Translations Overview: Backend error codes](../translations/overview/ui-and-errors.md#5-backend-error-codes-frontendsrcmystic_authapiapierrorts).

---
