#!/usr/bin/env bash
# Creates or refreshes the local-only operator used for browser and
# accessibility checks. This is not a production bootstrap command.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$REPO_ROOT"

COMPOSE=(docker compose
  -f docker/mystic_auth/compose/docker-compose.dev.yml
  -f docker/app/compose/docker-compose.dev.yml
  --env-file env/mystic_auth/.env.dev
  --env-file env/app/.env.dev)

ACCESSIBILITY_OPERATOR_ENV_FILE="${ACCESSIBILITY_OPERATOR_ENV_FILE:-$REPO_ROOT/.local/accessibility-operator.env}"
if [ ! -r "$ACCESSIBILITY_OPERATOR_ENV_FILE" ]; then
  echo "Missing $ACCESSIBILITY_OPERATOR_ENV_FILE. Create it with ACCESSIBILITY_OPERATOR_EMAIL and ACCESSIBILITY_OPERATOR_PASSWORD." >&2
  exit 1
fi
# shellcheck disable=SC1090
. "$ACCESSIBILITY_OPERATOR_ENV_FILE"
: "${ACCESSIBILITY_OPERATOR_EMAIL:?ACCESSIBILITY_OPERATOR_EMAIL is missing}"
: "${ACCESSIBILITY_OPERATOR_PASSWORD:?ACCESSIBILITY_OPERATOR_PASSWORD is missing}"
export ACCESSIBILITY_OPERATOR_EMAIL ACCESSIBILITY_OPERATOR_PASSWORD

"${COMPOSE[@]}" exec -T \
  -e EMAIL_ENABLED=false \
  -e ACCESSIBILITY_OPERATOR_EMAIL \
  -e ACCESSIBILITY_OPERATOR_PASSWORD \
  backend python - <<'PY'
import asyncio
import os

from mystic_auth.auth.password_logic.password_service import password_service
from mystic_auth.authorization.policies.default_policies import (
    SELF_SERVICE_POLICY_NAME,
    SYSTEM_SUPERUSER_POLICY_NAME,
    USER_MANAGEMENT_POLICY_NAME,
)
from mystic_auth.authorization.repositories.policy_repository import policy_repository
from mystic_auth.database.connection import database
from mystic_auth.user.user_crud_collector import user_crud
from mystic_auth.user.user_model import UserRole


async def main():
    email = os.environ["ACCESSIBILITY_OPERATOR_EMAIL"]
    password = os.environ["ACCESSIBILITY_OPERATOR_PASSWORD"]
    async for db in database.get_session():
        user = await user_crud.get_by_email(email, db)
        values = {
            "name": "Accessibility Test Operator",
            "email": email,
            "hashed_password": await password_service.hash_password(password),
            "role": UserRole.system,
            "is_verified": True,
            "is_active": True,
        }
        if user:
            await user_crud.update(user, values, db)
        else:
            user = await user_crud.create(values, db)
        for policy_name in (
            SELF_SERVICE_POLICY_NAME,
            USER_MANAGEMENT_POLICY_NAME,
            SYSTEM_SUPERUSER_POLICY_NAME,
        ):
            policy = await policy_repository.get_by_name(policy_name, db)
            if policy is None:
                raise RuntimeError(f"default policy missing: {policy_name}")
            await policy_repository.assign_policy_to_user(
                user.id, policy.id, db, assigned_by="accessibility-seed", user_email=email
            )
        await db.commit()
        print(f"seeded {email} as system user with 3 default policies")
        return


asyncio.run(main())
PY
