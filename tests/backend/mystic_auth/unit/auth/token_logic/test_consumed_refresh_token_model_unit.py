from sqlalchemy import BigInteger, DateTime, String

from backend.mystic_auth.auth.token_logic.consumed_refresh_token_model import ConsumedRefreshToken


def test_consumed_refresh_token_model_defines_durable_claim_columns():
    table = ConsumedRefreshToken.__table__

    assert table.name == "consumed_refresh_tokens"
    assert table.primary_key.columns.keys() == ["jti"]
    assert isinstance(table.c.jti.type, String)
    assert table.c.jti.type.length == 64
    assert isinstance(table.c.consumed_at.type, DateTime)
    assert table.c.consumed_at.nullable is False
    assert table.c.consumed_at.server_default is not None
    assert isinstance(table.c.expires_at.type, DateTime)
    assert table.c.expires_at.nullable is False
    assert table.c.expires_at.index is True
    assert isinstance(table.c.client_ip.type, String)
    assert table.c.client_ip.nullable is True
    assert isinstance(table.c.account_ver.type, BigInteger)
    assert isinstance(table.c.chain_ver.type, BigInteger)
