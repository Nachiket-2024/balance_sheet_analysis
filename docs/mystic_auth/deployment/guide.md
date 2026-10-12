# Deployment Guide
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

Shared deployment index for dev, local-prod, and prod. Use this page to choose a mode, then follow the mode-specific tutorial.

---

## 1. Deployment modes
---

| | Dev | Local-prod | Prod |
|---|---|---|---|
| Tutorial | [Dev Deployment](dev.md) | [Local-Prod Deployment](local-prod/README.md) | [Prod Deployment](prod.md) |
| Compose files | `docker/mystic_auth/compose/docker-compose.dev.yml` + `docker/app/compose/docker-compose.dev.yml` | Matching `docker/mystic_auth/compose/docker-compose.local-prod-{cloudflare,ngrok,tailscale}.yml` + `docker/app/compose/` overrides | `docker/mystic_auth/compose/docker-compose.prod.yml` + `docker/app/compose/docker-compose.prod.yml` |
| Frontend | Vite dev server with HMR | nginx static build | nginx static build |
| Source code | Bind-mounted from host | Baked into images | Baked into images |
| Backend reload | `--reload` | Off | Off |
| Public entrypoint | localhost only | Cloudflare, ngrok, or Tailscale tunnel | Caddy on a public server |
| TLS | None | Tunnel provider edge | Caddy and Let's Encrypt |
| Public server required | No | No | Yes |
| Host ports | Dev services on localhost | Debug ports offset per tunnel variant | Caddy only on 80/443 |

---

## 2. Shared references
---

| Topic | Reference |
|---|---|
| Environment file selection and required settings | [Environment and Runtime Configuration](environment.md) |
| Same-origin nginx routing and SPA/API route collisions | [Frontend and Backend Routing](routing.md) |
| Alembic migrations, backup scripts, scheduled dumps, and restore discipline | [Migrations and Backups](migrations-and-backups.md) |
| Graceful shutdown, host requirements, and deployment limitations | [Production Host Requirements](production-host.md) |
| Service-by-service Docker topology | [Docker Overview](../docker/overview.md) |
| Known operational gaps | [Known Issues and Technical Debt](../concerns/README.md) |

---

## 3. Recommended reading order
---

1. For local development, read [Dev Deployment](dev.md).
2. For a production-shaped local run through a tunnel, read [Local-Prod Deployment](local-prod/README.md), then one tunnel tutorial from that folder.
3. For a public server deployment, read [Prod Deployment](prod.md).
4. Before any production-shaped run, read [Environment and Runtime Configuration](environment.md).
5. Before relying on a deployment, read [Migrations and Backups](migrations-and-backups.md) and [Production Host Requirements](production-host.md).

---
