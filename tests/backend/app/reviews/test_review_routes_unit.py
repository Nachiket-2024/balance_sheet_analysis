from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from backend.app.api.review_routes import review_routes
from backend.app.reviews.review_schema import ReviewReportCreate


@pytest.mark.asyncio
async def test_create_review_requires_periods_and_persists_analysis(mocker):
    user = {"email": "reviewer@example.com"}
    db = SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    mocker.patch.object(review_routes, "_authorize_company", new_callable=AsyncMock)
    list_rows = mocker.patch.object(review_routes, "list_balance_sheets_for_company_years", new_callable=AsyncMock, return_value=[])
    payload = ReviewReportCreate(title="Annual review", years=[2024], notes="Board pack")
    with pytest.raises(HTTPException, match="At least one balance-sheet period is required"):
        await review_routes.create_company_review(9, payload, user, db)
    list_rows.return_value = [SimpleNamespace(year=2024)]
    analysis = SimpleNamespace(model_dump=Mock(return_value={"fiscal_years": [2024]}))
    mocker.patch.object(review_routes, "calculate_analysis", return_value=analysis)

    created = await review_routes.create_company_review(9, payload, user, db)

    assert created.company_id == 9
    assert created.created_by_email == user["email"]
    assert created.years == [2024]
    assert created.analysis == {"fiscal_years": [2024]}
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_review_and_add_comment_persist_author_and_notes(mocker):
    report = SimpleNamespace(id=12, status="draft", notes=None)
    mocker.patch.object(review_routes, "_authorize_report", new_callable=AsyncMock, return_value=report)
    db = SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    user = {"email": "reviewer@example.com"}

    updated = await review_routes.update_review_report(
        12, SimpleNamespace(status="reviewed", notes="Checked"), user, db
    )
    assert updated.status == "reviewed"
    assert updated.notes == "Checked"
    comment = await review_routes.add_review_comment(12, SimpleNamespace(body="Please confirm cash balance"), user, db)
    assert comment.author_email == user["email"]
    assert comment.body == "Please confirm cash balance"
    assert db.add.call_count == 1
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_assign_review_and_signoff_update_report_status(mocker):
    report = SimpleNamespace(id=13, status="reviewed")
    mocker.patch.object(review_routes, "_authorize_report", new_callable=AsyncMock, return_value=report)
    db = SimpleNamespace(add=Mock(), commit=AsyncMock(), refresh=AsyncMock())
    user = {"email": "reviewer@example.com"}

    assignment = await review_routes.assign_review(13, SimpleNamespace(assigned_to_email="assignee@example.com"), user, db)
    assert assignment.assigned_to_email == "assignee@example.com"
    assert assignment.assigned_by_email == user["email"]
    signoff = await review_routes.signoff_review(13, SimpleNamespace(status="approved", note="Reviewed"), user, db)
    assert report.status == "approved"
    assert signoff.actor_email == user["email"]
    assert signoff.status == "approved"
    assert signoff.note == "Reviewed"
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_export_review_html_escapes_report_content_and_marks_it_as_screening(mocker):
    report = SimpleNamespace(
        id=12,
        company_id=7,
        created_by_email="reviewer@example.com",
        title="<Quarterly> review",
        status="draft",
        years=[2023],
        notes="<script>alert('xss')</script>",
        analysis={
            "fiscal_years": [2023],
            "trends": {"total_assets": [{"value": 123}]},
            "warnings": [{"message": "<unsafe warning>"}],
        },
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    mocker.patch.object(review_routes, "_authorize_report", return_value=report)

    response = await review_routes.export_review_report_html(12, {"email": "reviewer@example.com"}, object())

    assert response.media_type.startswith("text/html")
    assert response.charset == "utf-8"
    document = response.body.decode()
    assert "&lt;Quarterly&gt; review" in document
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in document
    assert "&lt;unsafe warning&gt;" in document
    assert "not accounting, tax, legal, or investment advice" in document
    assert "<script>alert" not in document


def test_review_create_schema_rejects_blank_or_oversized_titles():
    with pytest.raises(ValueError):
        ReviewReportCreate(title="")

    with pytest.raises(ValueError):
        ReviewReportCreate(title="x" * 256)


def test_review_create_schema_preserves_optional_years_and_notes():
    payload = ReviewReportCreate(title="Board review", years=[2024, 2023], notes="Discuss debt trend")

    assert payload.title == "Board review"
    assert payload.years == [2024, 2023]
    assert payload.notes == "Discuss debt trend"
