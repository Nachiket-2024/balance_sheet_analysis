# Structure: Then (14 April, 2026)

---

One Python package, one npm package, no docs folder, no tests folder, no CI.

```text
mystic-auth/
  backend/
    alembic/
    app/
      api/
        auth_routes/
        user_routes/
      auth/
        current_user/
        login/
        logout/
        logout_all/
        oauth2/
        password_logic/
        password_reset_confirm/
        password_reset_request/
        refresh_token_logic/
        security/
        signup/
        token_logic/
        verify_account/
      core/
      database/
      logging/
      valkey/
      scripts/
      taskiq_tasks/
      user_crud/
      user_table/
    requirements.txt
    alembic.ini
  frontend/
    src/
      api/
      auth/
        current_user/
        login/
        logout/
        logout_all/
        oauth2/
        password_reset_confirm/
        password_reset_request/
        signup/
        verify_account/
      core/
      dashboard/
      store/
    package.json
  docker/
    backend.Dockerfile
    frontend.Dockerfile
  demo_assets/
  docker-compose.yml
  .env.example
  README.md
```

---

A single `backend/app/` and `frontend/src/` held everything: no upstream/downstream split, no
`sdk.py`/`sdk.ts`, no `mystic_auth` package name yet. Redux was still the frontend state manager.
Access control was role-based (a `role` column on the `users` table), not policy-based. There was
no `tests/` folder, no `docs/` folder, and no CI workflow: verification was manual, screenshots
lived in `demo_assets/`, not `screenshots/`.

---

See [Now](folder-tree-now.md) for the current tree, or [What Changed](what-changed.md) for a summary.

---
