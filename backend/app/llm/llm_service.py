import httpx

from ..balance_sheets.balance_sheet_model import BalanceSheet
from .llm_config import GROQ_API_KEY, GROQ_API_URL, GROQ_MODEL

# A curated subset of the ~68 yfinance fields, enough to answer typical
# "how's this company doing" questions (assets/liabilities/equity/debt/
# liquidity/profitability-adjacent figures) without blowing up the prompt
# with every low-level line item on every requested year.
_KEY_METRICS = [
    "total_assets",
    "total_liabilities_net_minority_interest",
    "stockholders_equity",
    "total_debt",
    "net_debt",
    "current_assets",
    "current_liabilities",
    "working_capital",
    "cash_and_cash_equivalents",
    "retained_earnings",
    "inventory",
    "accounts_receivable",
]


def build_grounding_context(company_name: str, ticker: str, balance_sheets: list[BalanceSheet]) -> str:
    """
    Serializes real balance-sheet figures into plain text for the LLM
    prompt. This is what makes the chat feature "grounded": previously
    (to_arrange/backend/api/llm_routes.py) the BalanceSheet model was
    imported but never actually queried, so answers were pure LLM
    speculation with no real figures behind them.
    """
    if not balance_sheets:
        return f"No balance sheet data is currently on file for {company_name} ({ticker})."

    lines = [f"Balance sheet figures for {company_name} ({ticker}), in reporting currency:"]
    for sheet in sorted(balance_sheets, key=lambda s: s.year):
        lines.append(f"\nFiscal year {sheet.year}:")
        for field in _KEY_METRICS:
            value = getattr(sheet, field, None)
            if value is not None:
                lines.append(f"  - {field.replace('_', ' ')}: {value:,.0f}")
    return "\n".join(lines)


async def ask_groq(question: str, grounding_context: str) -> str:
    """
    Sends `question` to Groq's chat completions API with `grounding_context`
    as system-prompt context, so the model answers from the real figures
    rather than guessing. Raises RuntimeError on any non-2xx response or
    malformed payload; the route layer turns that into an HTTP 502.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not configured")

    system_prompt = (
        "You are a balance-sheet analysis assistant for company analysts and "
        "top-management. Answer the user's question using ONLY the balance "
        "sheet data provided below. Do not invent figures. If the data "
        "doesn't cover what's being asked, say so explicitly instead of "
        "guessing.\n\n" + grounding_context
    )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_API_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json={
                    "model": GROQ_MODEL,
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
