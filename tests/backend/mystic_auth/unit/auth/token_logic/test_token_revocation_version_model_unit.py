from backend.mystic_auth.auth.token_logic.token_revocation_version_model import (
    TokenRevocationVersion,
)


def test_token_revocation_version_model_declares_durable_key_and_counter():
    row = TokenRevocationVersion(key="user:7")

    assert row.key == "user:7"
    assert TokenRevocationVersion.__tablename__ == "token_revocation_versions"
    assert TokenRevocationVersion.__table__.c.version.nullable is False
    assert TokenRevocationVersion.__table__.c.updated_at.nullable is False
