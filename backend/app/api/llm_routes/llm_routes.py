from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...access.permissions import LLM_CHAT, RESOURCE_LLM
from ...access.scope import resource_scope_dict
from ...app_sdk import rate_limiter_service
from ...balance_sheets.balance_sheet_crud import list_balance_sheets_for_company_years
from ...companies.company_crud import get_company_by_id
from ...llm.llm_schema import ChatRequest, ChatResponse
from ...llm.llm_service import ask_groq, build_grounding_context
from ...sdk import authorization_service, database, get_current_user, get_or_404

router = APIRouter(prefix="/llm", tags=["llm"])


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
    company = await get_or_404(get_company_by_id(payload.company_id, db), "Company not found")

    await authorization_service.require(
        current_user["email"],
        LLM_CHAT,
        RESOURCE_LLM,
        db,
        resource=resource_scope_dict(company.id, company.group_root_id),
    )

    balance_sheets = await list_balance_sheets_for_company_years(company.id, payload.years, db)
    context = build_grounding_context(company.name, company.ticker, balance_sheets)

    try:
        answer = await ask_groq(payload.question, context)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return ChatResponse(answer=answer)
