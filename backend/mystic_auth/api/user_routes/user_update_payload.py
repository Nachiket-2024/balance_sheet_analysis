from fastapi import HTTPException, status

# UserUpdate's `password` field name intentionally does not match any column on
# the User model (only `hashed_password` is a real column); it must be hashed
# and renamed here before reaching user_crud.update, or the submitted password
# is silently discarded (set as an unmapped attribute SQLAlchemy never
# persists) and the account keeps its old/no password.
from ...auth.password_logic.password_service import password_service
from ...user_table.user_schema import UserUpdate


async def prepare_update_data(update_data: UserUpdate) -> dict:
    """
    Dumps only explicitly-set fields. If a plaintext `password` was submitted,
    validates its strength (same minimum as signup/password-reset) and
    replaces it with a real Argon2 hash under `hashed_password`.

    Shared by both user_self_service_routes.py (update_my_profile) and
    user_management_routes.py (update_any_user): both routes accept the same
    UserUpdate body and need this same password-strength-check-then-hash step
    before it ever reaches user_crud.update.
    """
    data = update_data.model_dump(exclude_unset=True)
    # Only ever consulted by update_my_profile's own current-password check
    # in the caller, never a real column, so it must not reach
    # user_crud.update (which would otherwise set it as a harmless but
    # sloppy unmapped attribute on the ORM object).
    data.pop("current_password", None)
    plain_password = data.pop("password", None)
    if plain_password is not None:
        if not await password_service.validate_password_strength(plain_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password does not meet minimum strength requirements",
            )
        data["hashed_password"] = await password_service.hash_password(plain_password)
    return data
