#!/usr/bin/env bash
# Keep operator-facing script entry points available from all three supported
# shells: Bash, PowerShell, and Windows Command Prompt/batch.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$REPO_ROOT"

FAILURES=0

check_cmd_wrappers() {
  local directory="$1" command_extension="$2" script
  while IFS= read -r script; do
    local stem="${script%.sh}"
    local name="$(basename "$script" .sh)"
    if [ ! -f "$stem.ps1" ] || [ ! -f "$stem.$command_extension" ]; then
      echo "FAIL: $script must have $name.ps1 and $name.$command_extension" >&2
      FAILURES=$((FAILURES + 1))
      continue
    fi
    if ! grep -Fq -- "$name.sh" "$stem.ps1" || ! grep -Fq -- "-ScriptPath" "$stem.ps1"; then
      echo "FAIL: $stem.ps1 does not delegate to $name.sh" >&2
      FAILURES=$((FAILURES + 1))
    fi
    if ! grep -Fq -- "$name.ps1" "$stem.$command_extension"; then
      echo "FAIL: $stem.$command_extension does not delegate to $name.ps1" >&2
      FAILURES=$((FAILURES + 1))
    fi
  done < <(find "$directory" -mindepth 2 -maxdepth 2 -type f -name '*.sh' -print | sort)
}

check_cmd_wrappers scripts/mystic_auth/db cmd
check_cmd_wrappers tests/scripts/mystic_auth/accessibility cmd

while IFS= read -r script; do
  stem="${script%.sh}"
  name="$(basename "$script" .sh)"
  if [ ! -f "$stem.ps1" ] || [ ! -f "$stem.bat" ]; then
    echo "FAIL: $script must have $name.ps1 and $name.bat" >&2
    FAILURES=$((FAILURES + 1))
  fi
done < <(find local-scripts/mystic_auth -maxdepth 2 -type f -name '*.sh' -print | sort)

if [ "$FAILURES" -ne 0 ]; then
  echo "FAIL: $FAILURES platform-wrapper regression(s)." >&2
  exit 1
fi

echo "PASS: operator-facing scripts have Bash, PowerShell, and Windows wrappers."
