Your own nginx server/location blocks, alongside upstream's
`docker/mystic_auth/nginx.frontend.conf`.

`docker/mystic_auth/dockerfiles/frontend.Dockerfile`'s production stage
copies this directory to `/etc/nginx/conf.d/app/` and
`nginx.frontend.conf` already includes `/etc/nginx/conf.d/app/*.conf;`
inside its `server` block - a fork's own `.conf` files here are picked
up automatically at build time, no Dockerfile edit needed. nginx's
`include` with a glob matching zero files is a no-op, not an error, so
this being empty by default is safe.

Add your own location block as its own file here, e.g. `my-route.conf`:

```nginx
location /my-route {
    proxy_pass http://my-service:8080;
}
```

nginx picks the most specific matching `location` regardless of file
order, so where your block lands among upstream's doesn't matter the
way it would in Caddy.

Ships empty; upstream never edits this file again.
