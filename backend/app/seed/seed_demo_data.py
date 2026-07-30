"""
Seeds a demonstration dataset for the access-control model described in
CLAUDE.md's problem statement: a company group (Reliance Industries, with
Jio Platforms and Reliance Retail Ventures as subsidiaries), a CEO scoped to
one subsidiary, a group executive (the Ambani family) scoped to the whole
group, and an analyst also scoped to the group (per this session's decision
that analysts are scoped the same way top-management is, not globally
unrestricted).

Run once, after migrations, from the backend/ directory:
    python -m app.seed.seed_demo_data

Idempotent: re-running skips any company/user that already exists by
ticker/email, so it's safe to run again after adding a new demo persona.
"""
import asyncio
import getpass

from ..access.permissions import (
    BALANCE_SHEET_DELETE,
    BALANCE_SHEET_IMPORT,
    BALANCE_SHEET_READ,
    COMPANY_READ,
    LLM_CHAT,
)
from ..app_sdk import password_service, policy_repository, user_crud
from ..companies.company_crud import create_company, get_company_by_ticker
from ..companies.company_schema import CompanyCreate
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


async def seed_demo_data() -> None:
    print("\n--- Demo Data Seed: Reliance Group ---")

    print("\nSet a password for the three demo accounts (analyst/CEO/group exec):")
    demo_password = getpass.getpass("Demo account password: ")

    async for db in database.get_session():
        reliance_id = await _get_or_create_company("Reliance Industries", "RELIANCE.NS", None, db)
        jio_id = await _get_or_create_company("Jio Platforms", "JIO.NS", reliance_id, db)
        retail_id = await _get_or_create_company("Reliance Retail Ventures", "RRVL.NS", reliance_id, db)

        analyst_id = await _get_or_create_user("analyst@example.com", "Reliance Group Analyst", demo_password, db)
        ceo_jio_id = await _get_or_create_user("ceo.jio@example.com", "Jio Platforms CEO", demo_password, db)
        group_exec_id = await _get_or_create_user("ambani@example.com", "Group Executive (Ambani)", demo_password, db)

        analyst_policy_id = await _get_or_create_scoped_policy(
            "analyst_reliance_group",
            "Analyst covering the Reliance group: reads and maintains balance sheet data, chats with the LLM.",
            [COMPANY_READ, BALANCE_SHEET_READ, BALANCE_SHEET_IMPORT, BALANCE_SHEET_DELETE, LLM_CHAT],
            "group_root_id",
            reliance_id,
            db,
        )
        ceo_policy_id = await _get_or_create_scoped_policy(
            "ceo_jio_platforms",
            "CEO of Jio Platforms: reads only their own company's data and chats with the LLM about it.",
            [COMPANY_READ, BALANCE_SHEET_READ, LLM_CHAT],
            "company_id",
            jio_id,
            db,
        )
        group_exec_policy_id = await _get_or_create_scoped_policy(
            "group_exec_reliance",
            "Group executive: reads every company in the Reliance group and chats with the LLM about any of them.",
            [COMPANY_READ, BALANCE_SHEET_READ, LLM_CHAT],
            "group_root_id",
            reliance_id,
            db,
        )

        await policy_repository.assign_policy_to_user(analyst_id, analyst_policy_id, db, assigned_by="system_seed")
        await policy_repository.assign_policy_to_user(ceo_jio_id, ceo_policy_id, db, assigned_by="system_seed")
        await policy_repository.assign_policy_to_user(
            group_exec_id, group_exec_policy_id, db, assigned_by="system_seed"
        )

        print(
            f"\nDone. Reliance Industries id={reliance_id}, Jio Platforms id={jio_id}, "
            f"Reliance Retail Ventures id={retail_id}"
        )
        print("Log in as analyst@example.com / ceo.jio@example.com / ambani@example.com with the password you set.")
        return


if __name__ == "__main__":
    asyncio.run(seed_demo_data())
