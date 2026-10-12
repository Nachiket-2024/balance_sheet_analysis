Your own Dockerfiles, alongside upstream's `docker/mystic_auth/dockerfiles/`
(`backend.Dockerfile`, `frontend.Dockerfile`, `backend-entrypoint.sh`).

Adding a whole new service (your own microservice, a worker, anything
beyond backend/frontend) needs three things, none of which touch
upstream-owned files:

1. Your Dockerfile here, e.g. `docker/app/dockerfiles/my-service.Dockerfile`.
2. The new service definition in your own
   `docker/app/compose/docker-compose.<mode>.yml` override - Compose lets
   an override file introduce a brand-new service name, not just override
   an existing one:

   ```yaml
   services:
     my-service:
       build:
         context: ../../..
         dockerfile: docker/app/dockerfiles/my-service.Dockerfile
       env_file:
         - ../../../env/mystic_auth/.env.dev
         - ../../../env/app/.env.dev
   ```

3. Repeat per mode (`dev`, `prod`, `local-prod-*`) for whichever modes
   should run it.

See [Docker: Compose Modes](../../../docs/mystic_auth/docker/compose-modes.md#two-files-per-mode-mystic_auth--app)
for the two-file-per-mode pattern this extends.

Ships empty; upstream never edits this file again.
