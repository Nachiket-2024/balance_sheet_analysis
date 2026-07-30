# tests/backend/app/llm/test_llm_chat_access_boundaries.py
#
# LLM chat is gated by the same company-scoped PBAC check as the underlying
# balance-sheet data (see llm_routes.py's own docstring). It proves a user
# can't ask about a company they can't already see, and that a real
# balance-sheet row actually reaches the (mocked) Groq prompt, i.e. the
# response is grounded, not just an authorized-but-empty call.
import uuid

import pytest
import pytest_asyncio
from backend.app.access.permissions import LLM_CHAT
from backend.app.balance_sheets.balance_sheet_model import BalanceSheet
from backend.app.companies.company_crud import create_company
from backend.app.companies.company_model import Company
from backend.app.companies.company_schema import CompanyCreate
from backend.mystic_auth.auth.verify_account.account_verification_service import account_verification_service
from backend.mystic_auth.authorization.policies.default_policies import SELF_SERVICE_POLICY_NAME
from backend.mystic_auth.authorization.repositories.policy_repository import policy_repository
from backend.mystic_auth.database.connection import database
from backend.mystic_auth.redis.client import redis_client
from backend.mystic_auth.user_crud.user_crud_collector import user_crud

PASSWORD = "StrongPass123!"


def _unique(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


async def _create_verified_user_with_policy(client, created_emails, email, condition_key, condition_value):
    signup_resp = await client.post("/auth/signup", json={"name": "Test User", "email": email, "password": PASSWORD})
    assert signup_resp.status_code == 200
    created_emails.append(email)

    token = await account_verification_service.create_verification_token(email)
    await redis_client.set(f"verify:{token}", "1", ex=600)
    verify_resp = await client.post("/auth/verify-account", json={"token": token})
    assert verify_resp.status_code == 200

    async with database.async_session() as session:
        user = await user_crud.get_by_email(email, session)

        self_service = await policy_repository.get_by_name(SELF_SERVICE_POLICY_NAME, session)
        await policy_repository.assign_policy_to_user(user.id, self_service.id, session, assigned_by="test")

        policy = await policy_repository.create(
            {
                "name": _unique("test_policy_llm_scope"),
                "actions": [LLM_CHAT],
                "resource_type": "*",
                "conditions": {"resource_attributes": {condition_key: condition_value}},
            },
            session,
        )
        await policy_repository.assign_policy_to_user(user.id, policy.id, session, assigned_by="test")

    login_resp = await client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert login_resp.status_code == 200
    return client


@pytest.fixture
def created_company_ids():
    ids: list[int] = []
    yield ids


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(created_company_ids):
    yield
    async with database.async_session() as session:
        for company_id in created_company_ids:
            await session.execute(BalanceSheet.__table__.delete().where(BalanceSheet.company_id == company_id))
            company = await session.get(Company, company_id)
            if company:
                await session.delete(company)
        await session.commit()
        for policy in await policy_repository.get_all(session):
            if policy.name.startswith("test_policy_llm_scope"):
                await policy_repository.delete(policy, session)


@pytest.mark.asyncio
async def test_chat_is_grounded_in_real_balance_sheet_figures(mocker, client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Grounded Co", ticker=_unique("GRND")), session)
        session.add(BalanceSheet(company_id=company.id, year=2023, total_assets=123_456.0))
        await session.commit()
    created_company_ids.append(company.id)

    captured_context = {}

    async def fake_ask_groq(question, grounding_context):
        captured_context["value"] = grounding_context
        return "mocked answer"

    mocker.patch("backend.app.api.llm_routes.llm_routes.ask_groq", side_effect=fake_ask_groq)

    email = _unique("chatuser") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, "company_id", company.id)

    resp = await client.post("/llm/chat", json={"company_id": company.id, "question": "How are total assets?"})

    assert resp.status_code == 200
    assert resp.json() == {"answer": "mocked answer"}
    # The real figure inserted above must actually reach the prompt context,
    # since this is what "grounded" means, not just an authorized call.
    assert "123,456" in captured_context["value"]
    assert "Grounded Co" in captured_context["value"]


@pytest.mark.asyncio
async def test_chat_is_denied_for_a_company_outside_the_callers_scope(mocker, client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Out Of Scope Co", ticker=_unique("OOS")), session)
    created_company_ids.append(company.id)

    ask_groq_mock = mocker.patch("backend.app.api.llm_routes.llm_routes.ask_groq")

    email = _unique("scopedout") + "@example.com"
    # Scoped to a company_id that isn't this one.
    await _create_verified_user_with_policy(client, created_emails, email, "company_id", company.id + 1_000_000)

    resp = await client.post("/llm/chat", json={"company_id": company.id, "question": "Anything?"})

    assert resp.status_code == 403
    ask_groq_mock.assert_not_called()


@pytest.mark.asyncio
async def test_chat_returns_502_when_groq_fails(mocker, client, created_emails, created_company_ids):
    async with database.async_session() as session:
        company = await create_company(CompanyCreate(name="Groq Down Co", ticker=_unique("GQD")), session)
    created_company_ids.append(company.id)

    mocker.patch(
        "backend.app.api.llm_routes.llm_routes.ask_groq",
        side_effect=RuntimeError("Groq API error (500): boom"),
    )

    email = _unique("groqdown") + "@example.com"
    await _create_verified_user_with_policy(client, created_emails, email, "company_id", company.id)

    resp = await client.post("/llm/chat", json={"company_id": company.id, "question": "Anything?"})

    assert resp.status_code == 502
