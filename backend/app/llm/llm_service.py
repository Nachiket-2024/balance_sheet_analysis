from datetime import UTC, datetime
from time import monotonic

import httpx

from ..balance_sheets.analysis_service import analysis_context, calculate_analysis
from ..balance_sheets.balance_sheet_model import BalanceSheet
from ..financial_statements.financial_statement_model import FinancialStatement
from .llm_config import GROQ_API_KEY, GROQ_API_URL, GROQ_MAX_TOKENS, GROQ_MODEL


async def probe_provider() -> tuple[bool, float | None, str | None, datetime]:
    """Check the configured OpenAI-compatible provider without spending tokens."""
    checked_at = datetime.now(UTC)
    if not GROQ_API_KEY:
        return False, None, "not_configured", checked_at
    models_url = GROQ_API_URL.removesuffix("/chat/completions").rstrip("/") + "/models"
    started = monotonic()
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(models_url, headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
        latency_ms = round((monotonic() - started) * 1000, 2)
        if response.is_success:
            return True, latency_ms, None, checked_at
        return False, latency_ms, f"http_{response.status_code}", checked_at
    except httpx.HTTPError:
        return False, round((monotonic() - started) * 1000, 2), "provider_unreachable", checked_at


def build_grounding_context(company_name: str, ticker: str, balance_sheets: list[BalanceSheet]) -> str:
    """
    Serializes real balance-sheet figures into plain text for the LLM
    prompt. This balance-sheet context is combined with curated income and
    cash-flow statement fields by the chat route.
    """
    if not balance_sheets:
        return f"No balance sheet data is currently on file for {company_name} ({ticker})."
    return analysis_context(calculate_analysis(0, balance_sheets), company_name, ticker)


def build_statement_context(statements: list[FinancialStatement]) -> str:
    """Render curated statement fields with stable source citation tokens."""
    if not statements:
        return "No income-statement or cash-flow data is currently on file."
    fields = (
        "total_revenue", "gross_profit", "operating_income", "ebitda", "pretax_income", "net_income",
        "operating_cash_flow", "capital_expenditure", "free_cash_flow", "investing_cash_flow",
        "financing_cash_flow", "end_cash_position",
    )
    lines = ["Curated income-statement and cash-flow figures:"]
    for statement in sorted(statements, key=lambda item: (item.statement_type, item.year)):
        lines.append(f"  {statement.statement_type} FY{statement.year}:")
        for field in fields:
            value = getattr(statement, field, None)
            if value is not None:
                lines.append(f"    [source:{statement.statement_type}:FY{statement.year}:{field}] {field}={value:,.2f}")
    return "\n".join(lines)


async def ask_groq(question: str, grounding_context: str) -> str:
    """
    Sends `question` to Groq's chat completions API with `grounding_context`
    as system-prompt context, so the model answers from the real figures
    rather than guessing. Raises RuntimeError on any non-2xx response or
    malformed payload; the route layer turns that into an HTTP 502.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("LLM_API_KEY or GROQ_API_KEY is not configured")

    system_prompt = (
        "You are a balance-sheet analysis assistant for company analysts and "
        "top-management. Answer the user's question using ONLY the balance "
        "sheet data, curated statement data, and deterministic calculations "
        "provided below. Distinguish reported figures, calculated metrics, and "
        "interpretation. Do not recalculate or invent figures. Cite every "
        "numeric claim with the exact [source:...] token supplied in the context. "
        "If the data doesn't cover what's being asked, say so explicitly. Do not "
        "introduce market data or provide accounting, legal, tax, or investment advice.\n\n" + grounding_context
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
                    "max_tokens": GROQ_MAX_TOKENS,
                    "temperature": 0,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": question},
                    ],
                },
            )
    except httpx.HTTPError as exc:
        # Network failure/timeout reaching Groq itself (as opposed to a real
        # HTTP error response, handled below): without this, an unreachable
        # or slow Groq API surfaces as an unhandled 500, not the clean 502
        # every other Groq failure mode below produces.
        raise RuntimeError(f"Failed to reach Groq API: {exc}") from exc

    if response.status_code != 200:
        raise RuntimeError(f"Groq API error ({response.status_code}): {response.text}")

    try:
        return response.json()["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, ValueError) as exc:
        # ValueError covers response.json()'s own JSONDecodeError, not just
        # a well-formed-but-unexpected shape (KeyError/IndexError).
        raise RuntimeError(f"Unexpected Groq API response shape: {response.text}") from exc
