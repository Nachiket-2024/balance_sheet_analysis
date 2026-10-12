import os
import subprocess
import sys
from importlib import import_module
from pathlib import Path

native_sdk = import_module("backend.app.sdk")
docker_sdk = import_module("app.sdk")


def test_docker_and_native_sdk_imports_share_extension_types() -> None:
    assert docker_sdk.ConditionHandler is native_sdk.ConditionHandler
    assert docker_sdk.register_condition_type is native_sdk.register_condition_type


def test_sdk_exposes_bootstrap_policy_and_user_services() -> None:
    assert docker_sdk.policy_repository is native_sdk.policy_repository
    assert docker_sdk.user_crud is native_sdk.user_crud
    assert callable(docker_sdk.database.get_session)
    assert callable(docker_sdk.get_logger)


def test_sdk_does_not_eagerly_import_configured_task_modules() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    environment = os.environ.copy()
    environment["PROCRASTINATE_TASK_IMPORT_PATHS"] = "tests.backend.app.test_app_sdk_module_identity"
    environment["PROCRASTINATE_WORKER_MIDDLEWARE_PATHS"] = (
        "tests.backend.app.test_app_sdk_module_identity:configured_worker_middleware"
    )
    result = subprocess.run(
        [sys.executable, "-c", "import backend.app.sdk"],
        cwd=repo_root,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


async def configured_worker_middleware(call_next, context, worker):
    return await call_next()
