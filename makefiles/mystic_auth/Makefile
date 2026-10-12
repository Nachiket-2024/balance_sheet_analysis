# Real Makefile targets - upstream-owned, do not hand-edit. Add your own
# targets in makefiles/app/Makefile instead: the root Makefile includes both,
# app's after this one, so an app target of the same name wins. See
# docs/mystic_auth/template-usage/cheatsheet.md for the full command list
# and docs/mystic_auth/template-usage/ownership-split.md for the split.
.PHONY: help quickstart dev backend-host prod local-prod-cloudflare local-prod-ngrok local-prod-tailscale \
	setup-env check-env rotate-secrets set-env-field superuser backup restore-drill backup-freshness sync \
	test-tooling test-sync test-backup-freshness lint-paths lint-split lint

help:
	@echo "make quickstart              fresh clone -> working login, one command"
	@echo "make dev                     bring the dev stack up"
	@echo "make backend-host            run FastAPI on the host with Docker data services"
	@echo "make prod                    bring docker-compose.prod.yml up"
	@echo "make local-prod-cloudflare   local-prod behind a Cloudflare tunnel"
	@echo "make local-prod-ngrok        local-prod behind an ngrok tunnel"
	@echo "make local-prod-tailscale    local-prod behind Tailscale Funnel"
	@echo "make setup-env               bootstrap env files (app name, brand color, OAuth/email prompts)"
	@echo "make check-env               preflight check before local-prod/prod"
	@echo "make rotate-secrets          rotate SECRET_KEY/BUGSINK_SECRET_KEY"
	@echo "make set-env-field           set one field across every env file"
	@echo "make superuser               create/promote the system superuser (dev stack)"
	@echo "make backup                  dump the dev database"
	@echo "make restore-drill           prove the dev database's dump actually restores"
	@echo "make backup-freshness        verify required backups are recent and non-empty"
	@echo "make sync                    pull in upstream template updates"
	@echo "make test-tooling            regression suite for env-tools scripts"
	@echo "make test-sync               regression suite for sync-upstream.sh"
	@echo "make test-backup-freshness   regression suite for backup-freshness-check.sh"
	@echo "make lint-paths              check every ci/scripts/local-scripts path reference resolves"
	@echo "make lint-split              check for stale pre-split docker/env/scripts references"
	@echo "make lint                    run lint-paths and lint-split together"
	@echo
	@echo "See docs/mystic_auth/template-usage/cheatsheet.md for details."

quickstart:
	./scripts/mystic_auth/env-tools/quickstart/quickstart.sh

dev:
	./scripts/mystic_auth/docker/dev/dev-up.sh

backend-host:
	./scripts/mystic_auth/docker/dev/backend-host-run.sh

prod:
	./scripts/mystic_auth/docker/prod/prod-up.sh

local-prod-cloudflare:
	./scripts/mystic_auth/docker/local-prod-cloudflare/local-prod-cloudflare-up.sh

local-prod-ngrok:
	./scripts/mystic_auth/docker/local-prod-ngrok/local-prod-ngrok-up.sh

local-prod-tailscale:
	./scripts/mystic_auth/docker/local-prod-tailscale/local-prod-tailscale-up.sh

setup-env:
	./scripts/mystic_auth/env-tools/setup-env/setup-env.sh

check-env:
	./scripts/mystic_auth/env-tools/check-env/check-env.sh

rotate-secrets:
	./scripts/mystic_auth/env-tools/rotate-secrets/rotate-secrets.sh

set-env-field:
	./scripts/mystic_auth/env-tools/set-env-field/set-env-field.sh

superuser:
	docker compose \
	  -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml \
	  exec -it backend python -m mystic_auth.scripts.create_system_user

backup:
	./scripts/mystic_auth/db/database-backup/database-backup.sh

restore-drill:
	./scripts/mystic_auth/db/database-restore/database-restore-drill.sh

backup-freshness:
	./scripts/mystic_auth/db/backup-verification/backup-freshness-check.sh

sync:
	./scripts/mystic_auth/upstream-sync/sync-upstream.sh

test-tooling:
	ci/mystic_auth/tooling.sh env-tools

test-sync:
	ci/mystic_auth/tooling.sh upstream-sync

test-backup-freshness:
	ci/mystic_auth/tooling.sh backup-freshness

lint-paths:
	ci/mystic_auth/tooling.sh script-paths

lint-split:
	ci/mystic_auth/tooling.sh split-paths

lint: lint-paths lint-split
