# Import FastAPI's router class to define grouped endpoints for admin
from fastapi import APIRouter, Depends, HTTPException

# Import JSON response type for sending structured responses
from fastapi.responses import JSONResponse

# Import the User model so we can return or inspect the logged-in user
from ..models.user_model import User

# Import the method to get the current user from cookies (already authenticated)
from ..auth.auth_routes import get_current_user_from_cookie

# Create a router instance for grouping admin-only routes
router = APIRouter(tags=["Admin"])


# Define an endpoint to verify admin access
@router.get("/admin/ping")
def admin_ping(current_user: User = Depends(get_current_user_from_cookie)) -> JSONResponse:
    """
    A protected admin-only endpoint that:
    - Verifies the user is an admin using `get_current_user_from_cookie` dependency.
    - Returns a message and the admin's email if the user is an admin.
    """
    
    # Check if the user is an admin (role check)
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    # Return success message for admin
    return JSONResponse(
        content={
            "message": "Admin access verified",
            "admin_email": current_user.email
        }
    )
