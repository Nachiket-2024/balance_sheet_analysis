#!/usr/bin/env bash
# Preflight check for a real env/mystic_auth/.env* or env/app/.env* file:
# catches the two mistakes that
# otherwise only surface as a cryptic runtime error, a silently insecure
# deployment, or Docker's raw "port is already allocated" failure.
#
#   1. ERROR (exit 1): ENVIRONMENT=production in this file, but a secret
#      still equals the shipped placeholder from its .example. Shipping
#      that live means anyone who has ever seen the public template's
#      source can sign your JWTs or read your database.
#   2. ERROR (exit 1): a real env file is readable by group/other users. Env
#      files contain signing keys and database credentials and must be mode 600.
#   3. ERROR (exit 1): a Tailscale env file declares TS_CERT_DOMAIN but its
#      public origin/issuer/redirect host does not match that exact provider
#      DNS name. This prevents a stale tunnel hostname from reaching users.
#   4. WARNING (exit 0, printed): a <your_...>/<your-domain> placeholder is
#      still present (OAuth, SMTP, or a tunnel/domain field), or a host
#      port this file declares is already bound by something else on this
#      machine.
#
# Usage: scripts/mystic_auth/env-tools/check-env/check-env.sh [env/mystic_auth/.env.dev ...]
# With no arguments, checks every env/mystic_auth/.env* and env/app/.env*
# file that actually exists.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/../../../.."

FILES=("$@")
if [ "${#FILES[@]}" -eq 0 ]; then
  # Globs rather than a fixed list, so a fork's own new mode (e.g. a
  # hand-added env/app/.env.staging) is checked too, with no edit to this
  # upstream-owned script ever required.
  for candidate in env/mystic_auth/.env* env/app/.env*; do
    case "$candidate" in
      *.example|*.bak|*.ci-created) continue ;;
    esac
    [ -f "$candidate" ] && FILES+=("$candidate")
  done
fi

if [ "${#FILES[@]}" -eq 0 ]; then
  echo "No env files found to check. Run scripts/mystic_auth/env-tools/setup-env/setup-env.sh first." >&2
  exit 1
fi

PLACEHOLDER_SECRETS=(
  "SECRET_KEY=change_me_in_production_generate_your_own_random_32plus_char_key"
  "BUGSINK_SECRET_KEY=change_me_in_production_generate_your_own_random_50plus_char_key"
  "POSTGRES_PASSWORD=change_me_in_production"
  "APP_DB_PASSWORD=change_me_in_production"
  "BUGSINK_SUPERUSER_PASSWORD=change_me_in_production"
  "VALKEY_PASSWORD=change_me_in_production"
  "BACKUP_ENCRYPTION_KEY=change_me_in_production"
)

port_in_use() {
  # Portable-enough TCP probe: works without nc/lsof/ss being installed.
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null && exec 3<&- 3>&-
}

HAS_ERROR=0
HAS_WARNING=0

for f in "${FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "skip (not found): $f"
    continue
  fi

  echo "=== $f ==="
  is_prod=0
  grep -qE '^ENVIRONMENT=production$' "$f" && is_prod=1

  # Do not print permissions or file contents beyond the safe path. A mode
  # such as 644 is a production credential disclosure even when the values
  # themselves are otherwise strong. Exact 600 keeps the policy portable and
  # makes accidental group/other access impossible.
  file_mode="$(stat -c '%a' "$f" 2>/dev/null || stat -f '%Lp' "$f" 2>/dev/null || true)"
  if [ "$file_mode" != "600" ]; then
    echo "  ERROR: env file permissions must be exactly 600 (owner read/write only); current mode is not acceptable."
    HAS_ERROR=1
  fi

  # A Tailscale Funnel hostname is assigned by the tailnet, not derived from
  # TS_HOSTNAME. Requiring the operator to record the actual DNSName makes the
  # origin configuration self-checking and catches the class of stale-host
  # failure that otherwise only appears as invalid-host responses in public.
  ts_cert_domain="$(grep -m1 '^TS_CERT_DOMAIN=' "$f" | cut -d= -f2- || true)"
  if [ -n "$ts_cert_domain" ]; then
    public_origin="$(grep -m1 '^FRONTEND_BASE_URL=' "$f" | cut -d= -f2- || true)"
    public_host="${public_origin#*://}"
    public_host="${public_host%%/*}"
    public_host="${public_host%%:*}"
    if [ "$public_host" != "$ts_cert_domain" ]; then
      echo "  ERROR: FRONTEND_BASE_URL host does not match TS_CERT_DOMAIN. Use the exact DNSName reported by 'tailscale status --json'."
      HAS_ERROR=1
    fi
    for origin_var in JWT_ISSUER JWT_AUDIENCE GOOGLE_REDIRECT_URI; do
      origin_value="$(grep -m1 "^${origin_var}=" "$f" | cut -d= -f2- || true)"
      origin_host="${origin_value#*://}"
      origin_host="${origin_host%%/*}"
      origin_host="${origin_host%%:*}"
      if [ "$origin_host" != "$ts_cert_domain" ]; then
        echo "  ERROR: $origin_var host does not match TS_CERT_DOMAIN. Keep all public auth origins on the exact Funnel DNSName."
        HAS_ERROR=1
      fi
    done
  fi

  if [ "$is_prod" -eq 1 ]; then
    for entry in "${PLACEHOLDER_SECRETS[@]}"; do
      key="${entry%%=*}"
      if grep -qxF "$entry" "$f"; then
        echo "  ERROR: $key is still the shipped placeholder, but ENVIRONMENT=production."
        HAS_ERROR=1
      fi
    done

    backup_key_line="$(grep -m1 '^BACKUP_ENCRYPTION_KEY=' "$f" || true)"
    backup_key="${backup_key_line#BACKUP_ENCRYPTION_KEY=}"
    if [ -z "$backup_key_line" ] || [ -z "$backup_key" ]; then
      echo "  ERROR: BACKUP_ENCRYPTION_KEY is blank, but ENVIRONMENT=production. Set a high-entropy key before starting backups."
      HAS_ERROR=1
    fi

    backup_upload_line="$(grep -m1 '^BACKUP_UPLOAD_COMMAND=' "$f" || true)"
    backup_upload="${backup_upload_line#BACKUP_UPLOAD_COMMAND=}"
    if [ -z "$backup_upload_line" ] || [ -z "$backup_upload" ]; then
      echo "  ERROR: BACKUP_UPLOAD_COMMAND is blank, but ENVIRONMENT=production. Set a command that uploads the encrypted dump and its .hmac sidecar off-host. The command must reference \$DUMP_FILE."
      HAS_ERROR=1
    elif ! printf '%s' "$backup_upload" | grep -q 'DUMP_FILE'; then
      echo "  ERROR: BACKUP_UPLOAD_COMMAND must reference \$DUMP_FILE so the backup hook uploads the generated dump (and its .hmac sidecar)."
      HAS_ERROR=1
    fi
  fi

  placeholders="$(grep -oE '<your[a-z_-]*>|<your-domain>' "$f" | sort -u || true)"
  if [ -n "$placeholders" ]; then
    echo "  WARNING: still has placeholder value(s): $(echo "$placeholders" | tr '\n' ' ')"
    HAS_WARNING=1
  fi

  # A blank or malformed BUGSINK_SUPERUSER_EMAIL isn't just insecure, it's a
  # hard startup failure: Bugsink's own prestart hook rejects it with
  # ValueError and crash-loops, and every service that depends_on bugsink
  # being healthy (alembic, backend, frontend in dev-compose) fails with it,
  # a real live failure mode found running this script's own suite.
  bugsink_email_line="$(grep -m1 '^BUGSINK_SUPERUSER_EMAIL=' "$f" || true)"
  if [ -n "$bugsink_email_line" ]; then
    bugsink_email="${bugsink_email_line#BUGSINK_SUPERUSER_EMAIL=}"
    if [ -z "$bugsink_email" ] || ! echo "$bugsink_email" | grep -qE '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'; then
      echo "  WARNING: BUGSINK_SUPERUSER_EMAIL is blank or not a valid email. Bugsink will crash-loop on startup and take backend/frontend down with it (they depend_on it being healthy). Set it to any valid-looking address, e.g. admin@example.com - it doesn't need to be a real inbox for local dev."
      HAS_WARNING=1
    fi
  fi

  # NGROK_DOMAIN must be a bare domain: the compose file builds the tunnel
  # command as --url=https://${NGROK_DOMAIN}, so a value that already
  # includes a scheme produces a malformed double-scheme URL and ngrok
  # refuses to start (ERR_NGROK_9038) - a hard startup failure, found
  # running this exact mistake against a live tunnel.
  ngrok_domain_line="$(grep -m1 '^NGROK_DOMAIN=' "$f" || true)"
  if [ -n "$ngrok_domain_line" ]; then
    ngrok_domain="${ngrok_domain_line#NGROK_DOMAIN=}"
    if echo "$ngrok_domain" | grep -qE '://'; then
      echo "  ERROR: NGROK_DOMAIN=$ngrok_domain still has a scheme (http:// or https://). It must be the bare domain only, e.g. NGROK_DOMAIN=your-app.ngrok-free.app - ngrok will fail to start with ERR_NGROK_9038 otherwise."
      HAS_ERROR=1
    fi
  fi

  for portvar in POSTGRES_HOST_PORT VALKEY_HOST_PORT BACKEND_HOST_PORT FRONTEND_HOST_PORT BUGSINK_HOST_PORT; do
    port="$(grep -m1 "^${portvar}=" "$f" | cut -d= -f2-)"
    [ -n "$port" ] || continue
    if port_in_use "$port"; then
      echo "  WARNING: $portvar=$port is already bound by something else on this machine."
      HAS_WARNING=1
    fi
  done

  if [ -f "$f.bak" ]; then
    echo "  WARNING: $f.bak still exists - a leftover plaintext copy of the old secrets. Delete it once you've confirmed $f is correct."
    HAS_WARNING=1
  fi

  echo
done

if [ "$HAS_ERROR" -eq 1 ]; then
  echo "Fix the ERROR(s) above before starting this stack. If it's a placeholder secret still set with ENVIRONMENT=production:"
  echo "  scripts/mystic_auth/env-tools/rotate-secrets/rotate-secrets.sh (SECRET_KEY/BUGSINK_SECRET_KEY only; see its own header for POSTGRES_PASSWORD/APP_DB_PASSWORD/BUGSINK_SUPERUSER_PASSWORD, which need a live-database step too)"
  exit 1
fi

if [ "$HAS_WARNING" -eq 1 ]; then
  echo "Warnings above won't stop the stack from starting, but review them first."
fi

exit 0
