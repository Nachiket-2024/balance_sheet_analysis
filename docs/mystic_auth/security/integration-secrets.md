# Downstream Integration Secrets

---

Product-specific credentials belong to the downstream application. MysticAuth
provides a small secret-provider contract; it does not store integration
credentials in its database or configuration model.

## Extension point

Implement `SecretProvider` in `backend/app/` and register your provider from
the downstream startup hook in `backend/app/app_sdk.py`. Import the public
contract from `app.sdk`:

```python
from app.sdk import SecretProvider, require_secret


class BillingSecrets:
    def __init__(self, provider: SecretProvider) -> None:
        self._provider = provider

    def api_key(self) -> str:
        return require_secret(self._provider, "BILLING_API_KEY")
```

`SecretProvider.get_secret(name)` reads one named value and returns `None`
when the value is absent. `require_secret(provider, name)` raises a clear
configuration error if the value is missing or empty. The built-in
`EnvironmentSecretProvider` reads only the requested variable from the
process environment and rejects names that are not valid environment
identifiers.

## Supplying values

For local development, provide values through the ignored app runtime env file
(`env/app/.env.dev`) or your local secret manager. For deployment, inject them
through the host's secret manager or the app-specific Compose configuration.
Keep secret values out of tracked `.example` files; examples should document
variable names and safe placeholders only. Keep product settings in
`backend/app/core/settings.py` and app-specific env templates under
`env/app/`.

Read a secret at the point the integration needs it. Do not dump the full
environment or secret mapping into logs, API responses, task arguments,
migrations, audit metadata, or JSON settings. Tests should inject a small fake
provider rather than relying on a developer's real credentials.

## Ownership

Provider implementations, integration clients, their settings, and tests
belong under `backend/app/` and `tests/backend/app/`. Do not add product
credentials or product-specific providers under `backend/mystic_auth/`; that
tree is upstream-owned. See [The `app/` + `mystic_auth/` Split](../template-usage/ownership-split.md)
and [Building On This Template](../template-usage/customization.md#backend-customization).

---
