from datetime import UTC, datetime

from sqlalchemy import select

from ..balance_sheets.balance_sheet_crud import import_balance_sheet
from ..balance_sheets.balance_sheet_model import BalanceSheet
from ..companies.company_model import Company
from ..financial_statements.financial_statement_crud import import_statement
from ..financial_statements.financial_statement_model import FinancialStatement
from ..sdk import database, procrastinate_app


@procrastinate_app.periodic(cron="0 4 * * *")
@procrastinate_app.task
async def refresh_latest_financial_periods(timestamp: int) -> int:
    """Refresh each company's latest stored periods once per day.

    The import-attempt tables provide per-period operator visibility. A
    provider failure for one company is logged in its import-attempt history
    and does not prevent unrelated companies from refreshing; the task raises
    after the batch so Procrastinate retries when any provider failure occurs.
    """
    del timestamp
    refreshed = 0
    failures = 0
    async with database.async_session() as session:
        companies = list((await session.execute(select(Company).order_by(Company.id))).scalars().all())
        for company in companies:
            latest_balance = (await session.execute(select(BalanceSheet).where(BalanceSheet.company_id == company.id).order_by(BalanceSheet.year.desc()).limit(1))).scalar_one_or_none()
            if latest_balance is not None:
                try:
                    await import_balance_sheet(company.id, latest_balance.year, company.ticker, session, refresh=True)
                    refreshed += 1
                except Exception:
                    failures += 1
            latest_statements = (await session.execute(select(FinancialStatement).where(FinancialStatement.company_id == company.id).order_by(FinancialStatement.year.desc()).limit(2))).scalars().all()
            for statement in latest_statements:
                try:
                    await import_statement(company.id, statement.statement_type, statement.year, company.ticker, session, refresh=True, period_type=statement.period_type, period_number=statement.period_number)
                    refreshed += 1
                except Exception:
                    failures += 1
    if failures:
        raise RuntimeError(f"Financial refresh completed with {failures} provider failure(s) at {datetime.now(UTC).isoformat()}")
    return refreshed
