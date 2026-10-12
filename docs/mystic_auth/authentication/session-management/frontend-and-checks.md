# Session Management: Frontend and Production Checks

---

*New to a term here? See the [Authentication & Sessions Glossary](../../glossary/authentication.md).*

## Frontend behavior

1. **Ownership.** `ActiveSessionsCard.tsx` (renamed from `ManageSessionsCard.tsx`) lives in its own top-level `frontend/src/mystic_auth/active_sessions/` folder, not nested under `dashboard/` - Dashboard, Account Settings, and the Audit Log and Rate Limits pages' device/location cells (`rateLimitsColumns.tsx`, `securityLogColumns.tsx`, `authorizationLogColumns.tsx`) all render it or its row-formatting helpers now, so it no longer has a single owning page. It owns its own API query and mutation (`useSessionsQuery.ts`/`useRevokeSessionMutation.ts`); device labels come from `parseUserAgent.ts`; failure and empty states are rendered locally by the card.

---

2. **Table.** `activeSessionsTable.tsx`'s columns are Device, Location, IP Address, Signed In, and Last Seen, plus a row-actions column - `ip_address` is its own column directly (no longer hidden behind a separate detail view), and Location shows `city`/`country` inline. There is no separate details dialog anymore (the old `SessionDetailsDialog.tsx` is gone): every session's full information is visible in the row itself, since the columns stopped truncating.

---

3. **Current session handling.** The current session's row shows the same "Log out" button as every other row, not a disabled or hidden one - but `onEnd` routes it differently underneath: `session.is_current` picks the dedicated logout endpoint (bumping just that one chain) instead of the ownership-checked revoke-by-id endpoint every other row uses. The user-facing label and confirm-dialog copy both say "Log out" for that row and "End session"/"Revoke" for the rest, so the distinction stays visible even though the button itself looks the same. The current session is excluded from bulk multi-select ("This device isn't selectable"), since a bulk "end selected" covering the caller's own live session would end the request making it.

---

4. **Cache hygiene across accounts.** None of the "me"-scoped TanStack Query caches (sessions, policy assignments, own audit history, last login) are keyed by email, so a stale response from whoever was previously logged in in this same browser tab could otherwise flash for the next account before its own refetch lands. `useLogoutMutation`, `useLogoutAllMutation`, and `setupAuthInterceptor.ts`'s session-expiry handler all `removeQueries` (not just invalidate) these keys on the way out; `useLoginMutation` also invalidates them on the way in, as a second layer, since a login can happen without an explicit prior logout in this same tab (e.g. after a silent session expiry elsewhere).

---

## Production checks

The session feature is covered by:

- Backend unit tests for session list/revoke handlers and session repository/service behavior.
- Backend integration tests using real Postgres and Valkey for multi-device login, refresh rotation, targeted revoke, self-revoke rejection, foreign-session rejection, logout, logout-all, and session cleanup after password/account lifecycle changes.
- Backend unit tests cover the SSE stream generator (`user_session/session_events.py`) against real Valkey Pub/Sub, including publish/subscribe, heartbeats, and disconnect handling. An integration test confirms that a targeted session revoke publishes. The `GET /auth/session-events` route itself is only integration-tested for its auth contract because httpx's ASGITransport test harness does not reliably support a held-open streaming response.
- Frontend integration tests for the Manage Sessions card list, loading, error, empty, current-session, and revoke flows, plus a unit test for `useSessionEventsStream` (connects only while authenticated, closes on unmount, invalidates the relevant queries on a push event).

---

See [Session Management](README.md) for the feature map.

---
