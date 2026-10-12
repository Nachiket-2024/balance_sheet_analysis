# Target definitions for the root make.ps1 - upstream-owned, do not
# hand-edit. Add your own targets in makefiles/app/make.ps1 instead: root
# make.ps1 merges $MysticAuthTargets (this file) with $AppTargets (that
# file), app's entries last, so a target of the same name overrides. See
# docs/mystic_auth/template-usage/ownership-split.md.
#
# A few targets (test-tooling, test-sync, lint-paths, lint-split, backup)
# only have a `.sh` implementation - the regression suites and
# database-backup.sh are dev tooling that assumes a POSIX shell, unlike every
# user-facing script, which ships `.sh`/`.ps1`/`.cmd`. Those shell out to
# `bash` here, which Git for Windows already provides
# (`C:\Program Files\Git\bin\bash.exe` on PATH as `bash`) if you have Git
# installed, same requirement as cloning this repo in the first place.

function Invoke-Bash {
    param(
        [string]$ScriptPath,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )
    $bash = Get-Command bash -ErrorAction SilentlyContinue
    if (-not $bash) {
        Write-Error "bash not found on PATH. Install Git for Windows (ships bash.exe) or run this from WSL/Git Bash instead."
        exit 1
    }
    & bash $ScriptPath @Arguments
    exit $LASTEXITCODE
}

$MysticAuthTargets = @{
    "help" = {
        Write-Host "make.ps1 quickstart              fresh clone -> working login, one command"
        Write-Host "make.ps1 dev                     bring the dev stack up"
        Write-Host "make.ps1 backend-host            run FastAPI on the host with Docker data services"
        Write-Host "make.ps1 prod                    bring docker-compose.prod.yml up"
        Write-Host "make.ps1 local-prod-cloudflare   local-prod behind a Cloudflare tunnel"
        Write-Host "make.ps1 local-prod-ngrok        local-prod behind an ngrok tunnel"
        Write-Host "make.ps1 local-prod-tailscale    local-prod behind Tailscale Funnel"
        Write-Host "make.ps1 setup-env               bootstrap env files (app name, brand color, OAuth/email prompts)"
        Write-Host "make.ps1 check-env               preflight check before local-prod/prod"
        Write-Host "make.ps1 rotate-secrets          rotate SECRET_KEY/BUGSINK_SECRET_KEY"
        Write-Host "make.ps1 set-env-field           set one field across every env file"
        Write-Host "make.ps1 superuser               create/promote the system superuser (dev stack)"
        Write-Host "make.ps1 backup                  dump the dev database (needs bash, see below)"
        Write-Host "make.ps1 restore-drill           prove the dev database's dump actually restores (needs bash)"
        Write-Host "make.ps1 backup-freshness        verify required backups are recent and non-empty (needs bash)"
        Write-Host "make.ps1 sync                    pull in upstream template updates"
        Write-Host "make.ps1 test-tooling            regression suite for env-tools scripts (needs bash)"
        Write-Host "make.ps1 test-sync               regression suite for sync-upstream.sh (needs bash)"
        Write-Host "make.ps1 test-backup-freshness   regression suite for backup freshness checks (needs bash)"
        Write-Host "make.ps1 lint-paths              check every ci/scripts/local-scripts path reference resolves (needs bash)"
        Write-Host "make.ps1 lint-split              check for stale pre-split docker/env/scripts references (needs bash)"
        Write-Host "make.ps1 lint                    run lint-paths and lint-split together (needs bash)"
        Write-Host ""
        Write-Host "See docs/mystic_auth/template-usage/cheatsheet.md for details."
    }
    "quickstart" = { & .\scripts\mystic_auth\env-tools\quickstart\quickstart.ps1 }
    "dev" = { & .\scripts\mystic_auth\docker\dev\dev-up.ps1 }
    "backend-host" = { & .\scripts\mystic_auth\docker\dev\backend-host-run.ps1 }
    "prod" = { & .\scripts\mystic_auth\docker\prod\prod-up.ps1 }
    "local-prod-cloudflare" = { & .\scripts\mystic_auth\docker\local-prod-cloudflare\local-prod-cloudflare-up.ps1 }
    "local-prod-ngrok" = { & .\scripts\mystic_auth\docker\local-prod-ngrok\local-prod-ngrok-up.ps1 }
    "local-prod-tailscale" = { & .\scripts\mystic_auth\docker\local-prod-tailscale\local-prod-tailscale-up.ps1 }
    "setup-env" = { & .\scripts\mystic_auth\env-tools\setup-env\setup-env.ps1 }
    "check-env" = { & .\scripts\mystic_auth\env-tools\check-env\check-env.ps1 }
    "rotate-secrets" = { & .\scripts\mystic_auth\env-tools\rotate-secrets\rotate-secrets.ps1 }
    "set-env-field" = { & .\scripts\mystic_auth\env-tools\set-env-field\set-env-field.ps1 }
    "superuser" = {
        docker compose `
            -f docker/mystic_auth/compose/docker-compose.dev.yml -f docker/app/compose/docker-compose.dev.yml `
            exec -it backend python -m mystic_auth.scripts.create_system_user
    }
    "backup" = { Invoke-Bash "scripts/mystic_auth/db/database-backup/database-backup.sh" }
    "restore-drill" = { Invoke-Bash "scripts/mystic_auth/db/database-restore/database-restore-drill.sh" }
    "backup-freshness" = { Invoke-Bash "scripts/mystic_auth/db/backup-verification/backup-freshness-check.sh" }
    "sync" = { & .\scripts\mystic_auth\upstream-sync\sync-upstream.ps1 }
    "test-tooling" = { Invoke-Bash "ci/mystic_auth/tooling.sh" "env-tools" }
    "test-sync" = { Invoke-Bash "ci/mystic_auth/tooling.sh" "upstream-sync" }
    "test-backup-freshness" = { Invoke-Bash "ci/mystic_auth/tooling.sh" "backup-freshness" }
    "lint-paths" = { Invoke-Bash "ci/mystic_auth/tooling.sh" "script-paths" }
    "lint-split" = { Invoke-Bash "ci/mystic_auth/tooling.sh" "split-paths" }
    "lint" = {
        Invoke-Bash "ci/mystic_auth/tooling.sh" "script-paths"
        Invoke-Bash "ci/mystic_auth/tooling.sh" "split-paths"
    }
}
