"""
Seeds a demonstration dataset for the access-control model described in
AGENTS.md's product brief: a company group (Microsoft Corporation, with
GitHub, Inc. and LinkedIn Corporation as illustrative subsidiaries), a CEO scoped
to one subsidiary, a group executive scoped to the whole group, and an analyst
also scoped to the group (per this session's decision
that analysts are scoped the same way top-management is, not globally
unrestricted).

Run once, after migrations, from the backend/ directory:
    python -m app.seed.seed_demo_data

Idempotent: re-running skips any company/user that already exists by
ticker/email, so it's safe to run again after adding a new demo persona.
"""
import asyncio
import getpass
from datetime import date

from sqlalchemy import select

from ..access.permissions import (
    BALANCE_SHEET_DELETE,
    BALANCE_SHEET_IMPORT,
    BALANCE_SHEET_READ,
    COMPANY_READ,
    LLM_CHAT,
)
from ..app_sdk import password_service, policy_repository, user_crud
from ..balance_sheets.balance_sheet_model import BalanceSheet
from ..companies.company_crud import create_company, get_company_by_ticker
from ..companies.company_schema import CompanyCreate
from ..financial_statements.financial_statement_model import FinancialStatement
from ..sdk import UserRole, database


async def _get_or_create_company(name: str, ticker: str, parent_id: int | None, db) -> int:
    existing = await get_company_by_ticker(ticker, db)
    if existing:
        return existing.id
    company = await create_company(CompanyCreate(name=name, ticker=ticker, parent_company_id=parent_id), db)
    print(f"  created company: {name} ({ticker}), id={company.id}")
    return company.id


async def _get_or_create_user(email: str, name: str, password: str, db) -> int:
    existing = await user_crud.get_by_email(email, db)
    if existing:
        return existing.id
    hashed_password = await password_service.hash_password(password)
    user = await user_crud.create(
        {
            "name": name,
            "email": email,
            "hashed_password": hashed_password,
            "role": UserRole.user,  # Display/grouping metadata only, see access/scope.py
            "is_verified": True,
            "is_active": True,
        },
        db,
    )
    print(f"  created user: {email} (password set interactively), id={user.id}")
    return user.id


async def _get_or_create_scoped_policy(
    name: str, description: str, actions: list[str], condition_key: str, condition_value: int, db
) -> int:
    existing = await policy_repository.get_by_name(name, db)
    if existing:
        return existing.id
    policy = await policy_repository.create(
        {
            "name": name,
            "description": description,
            "actions": actions,
            # "*": this one policy covers company/balance_sheet/llm resource
            # types at once, since all three use the same two condition
            # keys (company_id/group_root_id), see access/scope.py.
            "resource_type": "*",
            "conditions": {"resource_attributes": {condition_key: condition_value}},
            "is_active": True,
        },
        db,
        changed_by="system_seed",
    )
    print(f"  created policy: {name} ({condition_key}={condition_value})")
    return policy.id


async def _seed_demo_balance_sheets(company_ids: list[int], db) -> None:
    """Provide two local fixture years so the demo opens with real analysis.

    The values are illustrative reported-currency units, not investment data.
    This stays local and deterministic; users can replace the rows through the
    normal import path when they want actual Yahoo Finance figures.
    """
    for index, company_id in enumerate(company_ids):
        for year, multiplier in ((2022, 1.0), (2023, 1.08)):
            exists = await db.scalar(
                select(BalanceSheet.id).where(BalanceSheet.company_id == company_id, BalanceSheet.year == year)
            )
            if exists is not None:
                continue
            assets = (100_000_000 + index * 25_000_000) * multiplier
            current_assets = assets * 0.42
            current_liabilities = assets * (0.24 + index * 0.01)
            debt = assets * (0.18 + index * 0.02)
            cash = assets * (0.10 - index * 0.01)
            db.add(
                BalanceSheet(
                    company_id=company_id,
                    year=year,
                    period_end_date=date(year, 6, 30),
                    source_provider="demo_fixture",
                    currency_code="USD",
                    total_assets=assets,
                    total_liabilities_net_minority_interest=assets * 0.58,
                    stockholders_equity=assets * 0.42,
                    current_assets=current_assets,
                    current_liabilities=current_liabilities,
                    total_debt=debt,
                    net_debt=debt - cash,
                    cash_cash_equivalents_and_short_term_investments=cash,
                    receivables=assets * 0.08,
                    inventory=assets * 0.06,
                    long_term_debt=debt * 0.75,
                    net_ppe=assets * 0.31,
                )
            )
    await db.flush()


async def _seed_demo_financial_statements(company_ids: list[int], db) -> None:
    """Add annual income and cash-flow fixtures for the company detail panels."""
    for index, company_id in enumerate(company_ids):
        for year, growth in ((2022, 1.0), (2023, 1.07)):
            revenue = (198_270_000_000 + index * 18_000_000_000) * growth
            operating_cash_flow = (89_035_000_000 + index * 8_000_000_000) * growth
            fixtures = (
                ("income", {
                    "total_revenue": revenue,
                    "gross_profit": revenue * 0.684,
                    "operating_income": revenue * 0.420,
                    "ebitda": revenue * 0.501,
                    "pretax_income": revenue * 0.422,
                    "net_income": revenue * 0.367,
                }),
                ("cash_flow", {
                    "operating_cash_flow": operating_cash_flow,
                    "capital_expenditure": -revenue * 0.120,
                    "free_cash_flow": operating_cash_flow - revenue * 0.120,
                    "investing_cash_flow": -revenue * 0.153,
                    "financing_cash_flow": -revenue * 0.296,
                    "end_cash_position": revenue * 0.070,
                }),
            )
            for statement_type, values in fixtures:
                exists = await db.scalar(
                    select(FinancialStatement.id).where(
                        FinancialStatement.company_id == company_id,
                        FinancialStatement.statement_type == statement_type,
                        FinancialStatement.year == year,
                        FinancialStatement.period_type == "annual",
                    )
                )
                if exists is not None:
                    continue
                db.add(FinancialStatement(
                    company_id=company_id,
                    statement_type=statement_type,
                    year=year,
                    period_end_date=date(year, 6, 30),
                    period_type="annual",
                    period_number=0,
                    source_provider="demo_fixture",
                    currency_code="USD",
                    unit_scale=1,
                    source_fields=list(values),
                    **values,
                ))
    await db.flush()


async def seed_demo_data() -> None:
    print("\n--- Demo Data Seed: Microsoft Group Example ---")

    print("\nSet a password for the three demo accounts (analyst/CEO/group exec):")
    demo_password = getpass.getpass("Demo account password: ")

    async for db in database.get_session():
        microsoft_id = await _get_or_create_company("Microsoft Corporation", "MSFT", None, db)
        github_id = await _get_or_create_company("GitHub, Inc.", "GITHUB.DEMO", microsoft_id, db)
        linkedin_id = await _get_or_create_company("LinkedIn Corporation", "LINKEDIN.DEMO", microsoft_id, db)
        company_ids = [microsoft_id, github_id, linkedin_id]
        await _seed_demo_balance_sheets(company_ids, db)
        await _seed_demo_financial_statements(company_ids, db)

        analyst_id = await _get_or_create_user("maya.chen@demo.example", "Maya Chen", demo_password, db)
        ceo_github_id = await _get_or_create_user("leo.martins@demo.example", "Leo Martins", demo_password, db)
        group_exec_id = await _get_or_create_user("jordan.okafor@demo.example", "Jordan Okafor", demo_password, db)

        analyst_policy_id = await _get_or_create_scoped_policy(
            "analyst_microsoft_group",
            "Analyst covering the Microsoft group example: reads and maintains balance sheet data, chats with the LLM.",
            [COMPANY_READ, BALANCE_SHEET_READ, BALANCE_SHEET_IMPORT, BALANCE_SHEET_DELETE, LLM_CHAT],
            "group_root_id",
            microsoft_id,
            db,
        )
        ceo_policy_id = await _get_or_create_scoped_policy(
            "ceo_github",
            "CEO of GitHub, Inc.: reads only their own company's data and chats with the LLM about it.",
            [COMPANY_READ, BALANCE_SHEET_READ, LLM_CHAT],
            "company_id",
            github_id,
            db,
        )
        group_exec_policy_id = await _get_or_create_scoped_policy(
            "group_exec_microsoft",
            "Group executive: reads every company in the Microsoft group example and chats with the LLM about any of them.",
            [COMPANY_READ, BALANCE_SHEET_READ, LLM_CHAT],
            "group_root_id",
            microsoft_id,
            db,
        )

        await policy_repository.assign_policy_to_user(analyst_id, analyst_policy_id, db, assigned_by="system_seed")
        await policy_repository.assign_policy_to_user(ceo_github_id, ceo_policy_id, db, assigned_by="system_seed")
        await policy_repository.assign_policy_to_user(
            group_exec_id, group_exec_policy_id, db, assigned_by="system_seed"
        )

        print(
            f"\nDone. Microsoft Corporation id={microsoft_id}, GitHub, Inc. id={github_id}, "
            f"LinkedIn Corporation id={linkedin_id}"
        )
        print("Log in as maya.chen@demo.example / leo.martins@demo.example / jordan.okafor@demo.example with the password you set.")
        return


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
