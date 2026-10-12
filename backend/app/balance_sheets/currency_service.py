from copy import copy
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .balance_sheet_model import YFINANCE_COLUMN_NAMES, BalanceSheet
from .currency_model import CurrencyRate


async def list_currency_rates(company_id: int, db: AsyncSession) -> list[CurrencyRate]:
    result = await db.execute(select(CurrencyRate).where(CurrencyRate.company_id == company_id).order_by(CurrencyRate.effective_date.desc()))
    return list(result.scalars().all())


def normalize_rows(rows: list[BalanceSheet], target_currency: str, rates: list[CurrencyRate], display_scale: float = 1.0) -> tuple[list[BalanceSheet], dict[str, Any]]:
    target_currency = target_currency.upper()
    normalized: list[BalanceSheet] = []
    unavailable_years: list[int] = []
    used_rates: list[dict[str, Any]] = []
    for row in rows:
        source_currency = (row.currency_code or "").upper()
        effective_date = row.period_end_date or date(row.year, 12, 31)
        rate_record = None if source_currency == target_currency else next(
            (item for item in rates if item.source_currency == source_currency and item.target_currency == target_currency and item.effective_date <= effective_date),
            None,
        )
        conversion_rate = 1.0 if source_currency == target_currency else rate_record.rate if rate_record else None
        if conversion_rate is None:
            unavailable_years.append(row.year)
            normalized.append(row)
            continue
        cloned = copy(row)
        for field in YFINANCE_COLUMN_NAMES:
            value = getattr(cloned, field, None)
            if value is not None:
                setattr(cloned, field, float(value) * conversion_rate * float(row.unit_scale or 1.0) / display_scale)
        if source_currency != target_currency and rate_record is not None:
            used_rates.append({"from": source_currency, "to": target_currency, "rate": rate_record.rate, "effective_date": rate_record.effective_date.isoformat(), "source": rate_record.source, "source_url": rate_record.source_url})
        normalized.append(cloned)
    return normalized, {"target_currency": target_currency, "display_scale": display_scale, "used_rates": used_rates, "unavailable_years": sorted(set(unavailable_years))}
