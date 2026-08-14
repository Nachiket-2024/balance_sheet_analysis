from fastapi import HTTPException


class AppError(HTTPException):
    """
    HTTPException subclass that carries a stable machine-readable `code`
    (and optional `params` for messages with runtime-interpolated values,
    e.g. a policy name), alongside the existing English `detail` used for
    logs/Sentry. The global exception handler in app/main.py surfaces
    `code`/`params` in the JSON response so the frontend can translate the
    error into the user's chosen language via
    frontend/src/mystic_auth/translations/languages/*/errors.json, instead of
    displaying the raw English `detail` string.

    `detail` stays required (not derived from `code`) so call sites keep
    writing a real English sentence for logs/Sentry, same as a plain
    HTTPException today.
    """

    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str | list | dict,
        params: dict[str, str | int] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail)
        self.code = code
        self.params = params or {}
