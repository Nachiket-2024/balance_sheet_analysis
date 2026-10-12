Your own Caddy site blocks/snippets, alongside upstream's
`docker/mystic_auth/Caddyfile`.

Upstream's Caddyfile ends with `import /etc/caddy/app/*.caddy`, and
`docker-compose.prod.yml` already mounts this directory to that path -
a fork's own `.caddy` files here are picked up automatically, no compose
edit needed. Caddy's glob import with zero matches is a no-op, not an
error, so this being empty by default is safe.

Add a whole new site block (another domain, another reverse-proxied
service) as its own file here, e.g. `my-service.caddy`:

```caddyfile
{$MY_SERVICE_DOMAIN} {
	reverse_proxy my-service:8080
}
```

Adding a route *inside* the existing domain's block (e.g. another path
prefix on the same domain as the frontend/backend) needs a Shared-tier
edit to `docker/mystic_auth/Caddyfile` directly instead - a glob import
can't reach inside an existing block. See
[Using This Repository as a Template: the app/ + mystic_auth/ split](../../../docs/mystic_auth/template-usage/ownership-split.md).

Ships empty; upstream never edits this file again.
