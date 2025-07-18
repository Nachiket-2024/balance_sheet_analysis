# Import FastAPI's dependency injection system and error response tool
from fastapi import Depends, HTTPException

# Import `Annotated` to clearly type dependencies for FastAPI routes
from typing import Annotated

# Import the User model to check if the user has admin privileges
from ..models.user_model import User

# Import the function that retrieves the logged-in user from the cookie
from .auth_routes import get_current_user_from_cookie


# Define a dependency that ensures the current user is an admin
def require_admin(
    current_user: Annotated[User, Depends(get_current_user_from_cookie)]
) -> User:
    """
    Ensures the logged-in user has the 'admin' role.
    If not, raises a 403 Forbidden error.
    Otherwise, returns the user object to the calling route.
    """

    # Raise 403 if the user is not an admin
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # If user is an admin, return them so the route can proceed
    return current_user
