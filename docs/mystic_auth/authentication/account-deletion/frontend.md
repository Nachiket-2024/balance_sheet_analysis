# Account Deletion: Frontend

---

## Frontend behavior

`DeleteAccountCard.tsx` (`frontend/src/mystic_auth/account_settings/`) reads `hasPassword` off the
current user to decide which flow to render: a `PasswordInput` re-confirm field for password
accounts, or a plain confirm button for OAuth-only accounts. Either way it opens a `ConfirmDialog`
before submitting. On success:

- If the response is `{ confirmation_required: true }` (OAuth-only path), it shows a "check your
  email" state without navigating away, since the account and session are still both valid.
- Otherwise (password path), it clears every "me"-scoped TanStack Query cache (current user,
  sessions, own policies, own audit history, matching the same cache-clearing
  [Session Management](../session-management/frontend-and-checks.md#frontend-behavior) describes for logout) and navigates
  to `/login`.

`account_settings/confirm_delete/ConfirmDeleteAccountPage.tsx` is the public `/confirm-delete`
route the emailed link opens: it reads `token` from the query string, calls
`POST /users/me/confirm-delete`, and shows success/error/expired states. It renders outside
`AppLayout`/`ProtectedRoute` (like `/login`), since the caller may not have an active session on
whatever device they open the email link from.

---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Card["DeleteAccountCard.tsx\n(Account Settings)"]
    HasPassword{"hasPassword?"}
    PwField["Re-confirm current password\n(PasswordInput)"]
    OAuthBtn["Plain confirm button"]
    Confirm["ConfirmDialog"]
    Submit["DELETE /users/me"]
    Branch{"confirmation_required\nin response?"}
    Email["Show 'check your email' state\naccount + session still valid"]
    ClearCache["Clear every 'me'-scoped\nquery cache"]
    Login["Navigate to /login"]
    Link["Emailed confirm-delete link"]
    ConfirmPage["ConfirmDeleteAccountPage.tsx\n/confirm-delete (public, no session needed)"]
    ConfirmSubmit["POST /users/me/confirm-delete"]
    Result["Success / error / expired state"]

    Card --> HasPassword
    HasPassword -- "yes" --> PwField --> Confirm
    HasPassword -- "no (OAuth-only)" --> OAuthBtn --> Confirm
    Confirm --> Submit --> Branch
    Branch -- "yes, OAuth-only" --> Email
    Email -.->|"caller clicks the link later,\nany device"| Link
    Link --> ConfirmPage --> ConfirmSubmit --> Result
    Branch -- "no, password account" --> ClearCache --> Login

    classDef decision fill:#eff6ff,stroke:#3b82f6,color:#1e3a8a
    classDef terminal fill:#dcfce7,stroke:#16a34a,color:#14532d
    class HasPassword,Branch decision
    class Login,Result terminal
    linkStyle default stroke:#334155,stroke-width:2px
```

---

See [Account Deletion](README.md) for the feature map.

---
