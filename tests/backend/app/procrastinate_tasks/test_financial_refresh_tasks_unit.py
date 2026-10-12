from backend.app.sdk import procrastinate_app


def test_app_worker_registers_downstream_financial_refresh_task():
    assert any(path.endswith("app.procrastinate_tasks.financial_refresh_tasks") for path in procrastinate_app.import_paths)


def test_app_worker_registers_downstream_notification_task():
    assert any(path.endswith("app.procrastinate_tasks.analysis_notification_tasks") for path in procrastinate_app.import_paths)
