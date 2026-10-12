Set up this mystic-auth-based project for local development:

1. Check only whether env/mystic_auth/.env.dev and env/app/.env.dev exist (do
   not read their contents). If either runtime file is missing, run
   scripts/mystic_auth/env-tools/setup-env/setup-env.sh first because
   quickstart only auto-runs setup when the MysticAuth file is missing. If
   setup-env asks about Google OAuth or Gmail email, answer No for now; do not
   collect OAuth/email secrets in your agent context. If it asks for an app
   name and brand color, use the values I gave you when handing you this file
   (or ask me if I didn't give you any).
2. Run scripts/mystic_auth/env-tools/quickstart/quickstart.sh. If setup-env was
   already run in step 1, quickstart should reuse the generated files.
3. Once the stack is up and you've created the system superuser, run
   scripts/mystic_auth/env-tools/check-env/check-env.sh with no arguments. It
   checks every real env/mystic_auth/.env* and env/app/.env* file and reports
   placeholder field names without exposing values. Don't guess from memory.
   Port-in-use warnings for the host ports belonging to this running Docker
   stack are expected; distinguish those from ports occupied by another
   process. Use the configured *_HOST_PORT values rather than assuming the
   default ports.
4. For each remaining reported placeholder or warning, tell me what it means, whether it blocks
   startup, and what action is needed. For placeholders, also say what the value is for
   and where to get a real value
   (see docs/mystic_auth/template-usage/overview.md's OAuth/Email setup
   sections), then stop. Keep product-specific values in env/app/.env.dev; do not ask me to
   hand-edit backend/mystic_auth/, frontend/src/mystic_auth/, or tracked env/mystic_auth/*.example
   files. If a required template-owned runtime value is still missing, identify the field and
   tell me that it belongs to the deployment-managed env/mystic_auth runtime file rather than
   asking me to modify template source. If I want the same app-owned values applied everywhere,
   I'll copy
   scripts/mystic_auth/env-tools/set-env-field/shared-values.env.example to shared-values.env,
   fill it in myself, and tell you to run
   scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh. Either way, don't ask me to
   paste real values into this chat, and don't read or print any real secret
   value out of an env file yourself. App-only variables belong in env/app/;
   do not add them to upstream-owned MysticAuth files. Product-specific
   documentation and policy text belongs in the downstream-owned root
   README.md, SECURITY.md, and CONTRIBUTING.md or the relevant app-owned
   folders; do not treat those files as template sync targets.
5. Confirm the frontend and backend API docs are reachable using the
   configured FRONTEND_HOST_PORT and BACKEND_HOST_PORT values (defaults are
   http://localhost:5173 and http://localhost:8000/docs), and tell me if either
   isn't.
