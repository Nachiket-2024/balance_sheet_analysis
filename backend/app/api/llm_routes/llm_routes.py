from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import Integer, cast, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import LLM_CHAT, LLM_USAGE_READ_ALL, RESOURCE_LLM
from ...access.scope import resource_scope_dict
from ...app_sdk import rate_limiter_service
from ...balance_sheets.analysis_service import analysis_context, calculate_analysis
from ...balance_sheets.balance_sheet_crud import list_balance_sheets_for_company_years
from ...companies.company_crud import get_company_by_id
from ...financial_statements.financial_statement_crud import list_statements
from ...llm.llm_config import GROQ_API_KEY, GROQ_MAX_TOKENS, GROQ_MODEL, LLM_DAILY_CHAR_BUDGET, LLM_PROVIDER
from ...llm.llm_model import LLMFeedback, LLMProviderProbe, LLMUsage
from ...llm.llm_schema import (
    ChatFeedback,
    ChatRequest,
    ChatResponse,
    LLMAdminUsageEntry,
    LLMAdminUsageSummary,
    LLMProviderOperationsSummary,
    LLMProviderStatus,
    LLMUsageSummary,
)
from ...llm.llm_service import ask_groq, build_statement_context, probe_provider
from ...llm.llm_usage import daily_usage_chars, has_budget
from ...sdk import authorization_service, database, get_current_user, get_or_404

router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/status", response_model=LLMProviderStatus)
async def provider_status(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    del current_user
    reachable, latency_ms, error_code, checked_at = await probe_provider()
    db.add(LLMProviderProbe(provider=LLM_PROVIDER, model=GROQ_MODEL, reachable=reachable, latency_ms=latency_ms, error_code=error_code, checked_at=checked_at))
    await db.execute(delete(LLMProviderProbe).where(LLMProviderProbe.checked_at < checked_at - timedelta(days=30)))
    await db.commit()
    return LLMProviderStatus(provider=LLM_PROVIDER, model=GROQ_MODEL, configured=bool(GROQ_API_KEY), reachable=reachable, latency_ms=latency_ms, checked_at=checked_at, error_code=error_code)


@router.get("/usage", response_model=LLMUsageSummary)
async def usage_summary(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    since = datetime.now(UTC) - timedelta(days=1)
    result = await db.execute(select(func.count(LLMUsage.id), func.coalesce(func.sum(LLMUsage.input_chars + LLMUsage.output_chars), 0)).where(LLMUsage.user_email == current_user["email"], LLMUsage.created_at >= since))
    requests, characters_used = result.one()
    return LLMUsageSummary(provider=LLM_PROVIDER, model=GROQ_MODEL, daily_character_budget=LLM_DAILY_CHAR_BUDGET, characters_used=int(characters_used), requests=int(requests))


@router.get("/usage/admin", response_model=LLMAdminUsageSummary)
async def admin_usage_summary(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    since = datetime.now(UTC) - timedelta(days=1)
    await authorization_service.require(current_user["email"], LLM_USAGE_READ_ALL, RESOURCE_LLM, db)
    result = await db.execute(
        select(
            LLMUsage.user_email,
            func.count(LLMUsage.id),
            func.coalesce(func.sum(LLMUsage.input_chars + LLMUsage.output_chars), 0),
            func.sum(cast(LLMUsage.status == "failed", Integer)),
        )
        .where(LLMUsage.created_at >= since)
        .group_by(LLMUsage.user_email)
        .order_by(func.count(LLMUsage.id).desc())
        .limit(500)
    )
    users = [LLMAdminUsageEntry(user_email=email, requests=int(requests), characters_used=int(characters), failed_requests=int(failed or 0)) for email, requests, characters, failed in result.all()]
    return LLMAdminUsageSummary(provider=LLM_PROVIDER, model=GROQ_MODEL, since=since, total_requests=sum(item.requests for item in users), total_characters=sum(item.characters_used for item in users), failed_requests=sum(item.failed_requests for item in users), users=users)


@router.get("/operations/admin", response_model=LLMProviderOperationsSummary)
async def admin_provider_operations(current_user: dict = Depends(get_current_user), db: AsyncSession = Depends(database.get_session)):
    since = datetime.now(UTC) - timedelta(days=1)
    await authorization_service.require(current_user["email"], LLM_USAGE_READ_ALL, RESOURCE_LLM, db)
    result = await db.execute(
        select(
            func.count(LLMProviderProbe.id),
            func.sum(cast(LLMProviderProbe.reachable, Integer)),
            func.avg(LLMProviderProbe.latency_ms),
            func.max(LLMProviderProbe.checked_at),
        ).where(
            LLMProviderProbe.provider == LLM_PROVIDER,
            LLMProviderProbe.model == GROQ_MODEL,
            LLMProviderProbe.checked_at >= since,
        )
    )
    probes, reachable, average_latency, last_checked_at = result.one()
    last_result = await db.execute(
        select(LLMProviderProbe.error_code)
        .where(LLMProviderProbe.provider == LLM_PROVIDER, LLMProviderProbe.model == GROQ_MODEL, LLMProviderProbe.checked_at >= since)
        .order_by(LLMProviderProbe.checked_at.desc())
        .limit(1)
    )
    last_error_code = last_result.scalar_one_or_none()
    return LLMProviderOperationsSummary(
        provider=LLM_PROVIDER,
        model=GROQ_MODEL,
        since=since,
        probes=int(probes or 0),
        reachable_probes=int(reachable or 0),
        failed_probes=int((probes or 0) - (reachable or 0)),
        average_latency_ms=round(float(average_latency), 2) if average_latency is not None else None,
        last_checked_at=last_checked_at,
        last_error_code=last_error_code,
    )


@router.post("/chat", response_model=ChatResponse)
@rate_limiter_service.rate_limited("llm_chat", account_key_func=lambda kwargs: kwargs["current_user"]["email"])
async def chat(
    request: Request,
    payload: ChatRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    """
    Grounded chat: fetches the real balance-sheet rows for the requested
    company/years and injects them into the LLM prompt (see
    llm_service.build_grounding_context), instead of the pre-migration
    repo's ungrounded version, which imported BalanceSheet but never
    queried it. Gated with the same company-scoped PBAC check as the
    underlying data: a user can only ask about a company they can already
    see (see access/scope.py).

    Rate-limited (per-IP and per-account, see rate_limiter_service) since
    every request costs a real Groq API call; without this, one caller
    could run up API costs or exhaust the Groq rate limit for everyone.
    """
    company = await get_or_404(get_company_by_id(payload.company_id, db), "Company not found", code="COMPANY_NOT_FOUND")

    await authorization_service.require(
        current_user["email"],
        LLM_CHAT,
        RESOURCE_LLM,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )

    balance_sheets = await list_balance_sheets_for_company_years(company.id, payload.years, db)
    deterministic_analysis = calculate_analysis(company.id, balance_sheets, payload.years)
    context = analysis_context(deterministic_analysis, company.name, company.ticker)
    statements = await list_statements(company.id, None, db, years=payload.years)
    context += "\n\n" + build_statement_context(statements)

    if not has_budget(await daily_usage_chars(current_user["email"], db), payload.question, context):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily LLM usage budget exceeded")

    try:
        answer = await ask_groq(payload.question, context)
    except RuntimeError as exc:
        db.add(LLMUsage(user_email=current_user["email"], company_id=company.id, provider=LLM_PROVIDER, model=GROQ_MODEL, input_chars=len(payload.question) + len(context), output_chars=0, max_tokens=GROQ_MAX_TOKENS, status="failed", error_code=type(exc).__name__))
        await db.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    db.add(LLMUsage(user_email=current_user["email"], company_id=company.id, provider=LLM_PROVIDER, model=GROQ_MODEL, input_chars=len(payload.question) + len(context), output_chars=len(answer), max_tokens=GROQ_MAX_TOKENS, status="success"))
    await db.commit()

    return ChatResponse(answer=answer)


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
async def feedback(
    payload: ChatFeedback,
    company_id: int,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(database.get_session),
):
    company = await get_or_404(get_company_by_id(company_id, db), "Company not found", code="COMPANY_NOT_FOUND")
    await authorization_service.require(
        current_user["email"], LLM_CHAT, RESOURCE_LLM, db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )
    db.add(LLMFeedback(company_id=company_id, user_email=current_user["email"], helpful=payload.helpful, comment=payload.comment))
    await db.commit()
    return {"recorded": True}
