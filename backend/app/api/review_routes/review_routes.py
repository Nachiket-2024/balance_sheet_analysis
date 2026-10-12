from html import escape

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET
from ...access.scope import resource_scope_dict
from ...balance_sheets.analysis_service import calculate_analysis
from ...balance_sheets.balance_sheet_crud import list_balance_sheets_for_company_years
from ...companies.company_crud import get_company_by_id
from ...reviews.review_model import ReviewAssignment, ReviewComment, ReviewReport, ReviewSignoff
from ...reviews.review_schema import (
    ReviewAssignmentCreate,
    ReviewAssignmentResponse,
    ReviewCommentCreate,
    ReviewCommentResponse,
    ReviewReportCreate,
    ReviewReportResponse,
    ReviewReportStatusUpdate,
    ReviewSignoffCreate,
    ReviewSignoffResponse,
)
from ...sdk import authorization_service, database, get_current_user, get_or_404

router = APIRouter(prefix="/reviews", tags=["reviews"])


async def _authorize_company(company_id: int, current_user: dict, db: AsyncSession):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(
        current_user["email"], BALANCE_SHEET_READ, RESOURCE_BALANCE_SHEET, db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    return company


async def _authorize_report(report_id: int, current_user: dict, db: AsyncSession) -> ReviewReport:
    report = await get_or_404(db.get(ReviewReport, report_id), "Review report not found", code="REVIEW_REPORT_NOT_FOUND")
    await _authorize_company(report.company_id, current_user, db)
    return report


@router.get("/company/{company_id}", response_model=list[ReviewReportResponse])
async def list_company_reviews(
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorize_company(company_id, current_user, db)
    result = await db.execute(
        ReviewReport.__table__.select().where(ReviewReport.company_id == company_id).order_by(ReviewReport.updated_at.desc())
    )
    return list(result.mappings().all())


@router.post("/company/{company_id}", response_model=ReviewReportResponse, status_code=status.HTTP_201_CREATED)
async def create_company_review(
    company_id: int,
    payload: ReviewReportCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorize_company(company_id, current_user, db)
    rows = await list_balance_sheets_for_company_years(company_id, payload.years, db)
    if not rows:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one balance-sheet period is required")
    years = [row.year for row in rows]
    analysis = calculate_analysis(company_id, rows, years).model_dump(mode="json")
    report = ReviewReport(
        company_id=company_id,
        created_by_email=current_user["email"],
        title=payload.title,
        status="draft",
        years=years,
        analysis=analysis,
        notes=payload.notes,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/{report_id}", response_model=ReviewReportResponse)
async def get_review_report(
    report_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    return await _authorize_report(report_id, current_user, db)


@router.get("/{report_id}/export.html")
async def export_review_report_html(
    report_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    report = await _authorize_report(report_id, current_user, db)
    analysis = report.analysis
    trend_rows = []
    for metric in ("total_assets", "total_liabilities", "stockholders_equity", "total_debt"):
        series = analysis.get("trends", {}).get(metric, [])
        cells = "".join(f"<td>{escape(str(point.get('value') if point.get('value') is not None else 'Unavailable'))}</td>" for point in series)
        trend_rows.append(f"<tr><th>{escape(metric.replace('_', ' ').title())}</th>{cells}</tr>")
    years = "".join(f"<th>FY {escape(str(year))}</th>" for year in analysis.get("fiscal_years", []))
    warnings = "".join(f"<li>{escape(str(item.get('message', 'Review flag')))}</li>" for item in analysis.get("warnings", [])) or "<li>None</li>"
    document = f"""<!doctype html><html><head><meta charset='utf-8'><title>{escape(report.title)}</title><style>body{{font-family:system-ui,sans-serif;max-width:960px;margin:40px auto;padding:0 20px;color:#172033}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #ccd3df;padding:8px;text-align:right}}th:first-child,td:first-child{{text-align:left}}.meta{{color:#5c677d}}</style></head><body><h1>{escape(report.title)}</h1><p class='meta'>Company ID {report.company_id} · Periods: {escape(', '.join(map(str, report.years)))} · Status: {escape(report.status)} · Created by: {escape(report.created_by_email)}</p><h2>Core trends</h2><table><thead><tr><th>Metric</th>{years}</tr></thead><tbody>{''.join(trend_rows)}</tbody></table><h2>Review flags</h2><ul>{warnings}</ul><h2>Notes</h2><p>{escape(report.notes or 'No notes')}</p><p class='meta'>This report contains deterministic screening analysis from the stored provider data. It is not accounting, tax, legal, or investment advice.</p></body></html>"""
    return Response(
        content=document,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="review-{report.id}.html"'},
    )


@router.patch("/{report_id}", response_model=ReviewReportResponse)
async def update_review_report(
    report_id: int,
    payload: ReviewReportStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    report = await _authorize_report(report_id, current_user, db)
    report.status = payload.status
    if payload.notes is not None:
        report.notes = payload.notes
    await db.commit()
    await db.refresh(report)
    return report


@router.get("/{report_id}/comments", response_model=list[ReviewCommentResponse])
async def list_review_comments(
    report_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorize_report(report_id, current_user, db)
    result = await db.execute(
        ReviewComment.__table__.select().where(ReviewComment.review_report_id == report_id).order_by(ReviewComment.created_at)
    )
    return list(result.mappings().all())


@router.post("/{report_id}/comments", response_model=ReviewCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_review_comment(
    report_id: int,
    payload: ReviewCommentCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    await _authorize_report(report_id, current_user, db)
    comment = ReviewComment(review_report_id=report_id, author_email=current_user["email"], body=payload.body)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return comment


@router.get("/{report_id}/assignments", response_model=list[ReviewAssignmentResponse])
async def list_review_assignments(report_id: int, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    await _authorize_report(report_id, current_user, db)
    result = await db.execute(ReviewAssignment.__table__.select().where(ReviewAssignment.review_report_id == report_id).order_by(ReviewAssignment.created_at.desc()))
    return list(result.mappings().all())


@router.post("/{report_id}/assignments", response_model=ReviewAssignmentResponse, status_code=status.HTTP_201_CREATED)
async def assign_review(report_id: int, payload: ReviewAssignmentCreate, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    await _authorize_report(report_id, current_user, db)
    assignment = ReviewAssignment(review_report_id=report_id, assigned_to_email=payload.assigned_to_email, assigned_by_email=current_user["email"])
    db.add(assignment)
    await db.commit()
    await db.refresh(assignment)
    return assignment


@router.get("/{report_id}/signoffs", response_model=list[ReviewSignoffResponse])
async def list_review_signoffs(report_id: int, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    await _authorize_report(report_id, current_user, db)
    result = await db.execute(ReviewSignoff.__table__.select().where(ReviewSignoff.review_report_id == report_id).order_by(ReviewSignoff.created_at.desc()))
    return list(result.mappings().all())


@router.post("/{report_id}/signoffs", response_model=ReviewSignoffResponse, status_code=status.HTTP_201_CREATED)
async def signoff_review(report_id: int, payload: ReviewSignoffCreate, current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    report = await _authorize_report(report_id, current_user, db)
    report.status = payload.status
    signoff = ReviewSignoff(review_report_id=report_id, actor_email=current_user["email"], status=payload.status, note=payload.note)
    db.add(signoff)
    await db.commit()
    await db.refresh(signoff)
    return signoff
