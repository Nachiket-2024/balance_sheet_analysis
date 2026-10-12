# Frontend and Backend Routing
---

*New to a term here? See the [Infrastructure Glossary](../glossary/infrastructure.md).*

Production-shaped deployments use a single public origin by default. The frontend nginx container serves the SPA and proxies API prefixes to the backend service.

---

## 1. Same-origin API proxy
---

```mermaid
%%{init: {"themeVariables": {"lineColor": "#334155"}} }%%
flowchart TD
    Browser["Browser request"] --> Nginx["nginx\n (frontend container)"]
    Nginx --> Check{"Path starts with\n /auth, /audit, /users,\n /authorization, /health,\n or /rate-limits?"}
    Check -->|"Yes"| Backend["Proxy to backend:8000"]
    Check -->|"No"| Static["Serve static SPA build\n (index.html for unknown paths)"]
    linkStyle default stroke:#334155,stroke-width:2px
```

`docker/mystic_auth/nginx.frontend.conf` forwards these prefixes to `backend:8000`:

1. `/auth`
2. `/audit`
3. `/users`
4. `/authorization`
5. `/health`
6. `/rate-limits`

This works when `VITE_API_BASE_URL` is empty. The browser calls the same origin that served the SPA, and nginx handles the backend hop inside Docker.

---

## 2. Trusted proxy IPs
---

Each production-shaped Compose file pins frontend and tunnel proxy containers to fixed addresses (`FRONTEND_STATIC_IP` and a tunnel-specific `*_STATIC_IP` var, both set in the matching `env/mystic_auth/.env*` file) so the backend can safely trust `X-Forwarded-For` from those hops. Each compose file derives `TRUSTED_PROXY_IPS` for the backend service directly from those same two vars, rather than setting it independently in the env file, so it can never drift out of sync with the actual pinned addresses.

| Compose file | Frontend IP var | Tunnel/proxy IP var |
|---|---|---|
| `docker-compose.local-prod-cloudflare.yml` | `FRONTEND_STATIC_IP` | `CLOUDFLARED_STATIC_IP` |
| `docker-compose.local-prod-ngrok.yml` | `FRONTEND_STATIC_IP` | `NGROK_STATIC_IP` |
| `docker-compose.local-prod-tailscale.yml` | `FRONTEND_STATIC_IP` | `TAILSCALE_STATIC_IP` |
| `docker-compose.prod.yml` | `FRONTEND_STATIC_IP` | `CADDY_STATIC_IP` |

Both vars must stay inside that file's `DOCKER_SUBNET`. See [Docker: Compose Modes](../docker/compose-modes.md#two-forks-of-this-template-collide-with-each-other-too) for why these are env vars rather than hardcoded, and each `env/mystic_auth/.env*.example` for the actual default addresses.

`proxy_add_x_forwarded_for` appends instead of overwriting, preserving the client IP chain.

---

## 3. Route collision handling
---

The SPA and API share one origin, so a top-level SPA route can collide with an API prefix. `/users` and `/rate-limits` are both SPA pages and backend prefixes.

Client-side navigation does not hit nginx, but hard refreshes and bookmarks do. Without exact-match overrides, nginx can return backend JSON instead of `index.html`.

`docker/mystic_auth/nginx.frontend.conf` fixes those two collisions with exact-match locations:

```nginx
location = /users {
    try_files /index.html /index.html;
}
location = /rate-limits {
    try_files /index.html /index.html;
}
```

These exact paths are safe because frontend API calls use `/users/`, `/users/{email}`, `/rate-limits/`, or `/rate-limits/{key}`, not bare `/users` or `/rate-limits`.

---

## 4. Adding a new colliding route
---

If a new SPA route starts with an API prefix, add an exact-match nginx carve-out for the frontend route.

```nginx
location = /health-status {
    try_files /index.html /index.html;
}
```

Do this only for concrete SPA routes that collide. Do not remove the API proxy prefixes.

---

## 5. Split frontend deployment
---

If the frontend is hosted outside this nginx container:

1. Set `VITE_API_BASE_URL` to the backend public origin.
2. Set backend CORS values with `FRONTEND_BASE_URL` and `FRONTEND_ADDITIONAL_BASE_URLS`.
3. Set `TRUSTED_PROXY_IPS` to the proxy that actually sits in front of the backend.
4. Rebuild the frontend bundle after changing `VITE_API_BASE_URL`.

---
