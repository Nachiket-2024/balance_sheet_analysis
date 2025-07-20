# Import OS module to read environment variables
import os

# FastAPI imports for routing and HTTP handling
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import Request

# SQLAlchemy import to manage DB sessions
from sqlalchemy.orm import Session

# Load environment variables from a .env file
from dotenv import load_dotenv

# JWT error for handling invalid token scenarios
from jose import JWTError

# Used to extract token from Authorization header (for protected routes)
from fastapi.security import OAuth2PasswordBearer

# Internal utility functions for auth logic
from .auth_utils import authenticate_with_google, create_jwt_token, verify_jwt_token

# Import models for users and admins
from ..models.user_model import User
from ..models.admin_model import Admin

# Import DB session getter
from ..db.session import get_db

# Load environment variables defined in .env (like client ID/secret)
load_dotenv()

# This scheme allows token extraction from the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create the router with a prefix and tag for Swagger docs
router = APIRouter(
    prefix="/auth",           # All auth routes will begin with /auth
    tags=["Authentication"],  # Group these routes under "Authentication" in docs
)

# ---------------------------- Route: Google Login Initiation ----------------------------

@router.get("/login")
async def login_with_google(request: Request, db: Session = Depends(get_db)):
    """
    Initiates the Google OAuth2 flow.
    Redirects the user to the Google authentication page.
    """
    try:
        # Google OAuth endpoint
        google_oauth_url = "https://accounts.google.com/o/oauth2/v2/auth"

        # Construct the full redirect URL with required OAuth params
        auth_url = (
            f"{google_oauth_url}?response_type=code"
            f"&client_id={os.getenv('GOOGLE_CLIENT_ID')}"
            f"&redirect_uri={os.getenv('GOOGLE_REDIRECT_URI')}"
            f"&scope=openid%20email"
        )

        # Redirect user to Google’s login
        return RedirectResponse(url=auth_url)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth2 Authentication Failed: {str(e)}")

# ---------------------------- Route: OAuth2 Callback ----------------------------

@router.get("/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle the Google OAuth2 callback and exchange the authorization code for a JWT token.
    """
    try:
        # Step 1: Exchange code for user info (Google email, etc.)
        user_info = authenticate_with_google(code, db)

        # Step 2: Check if the user is an admin (priority)
        admin = db.query(Admin).filter(Admin.email == user_info['email']).first()

        # Step 3: Determine role
        if admin:
            role = "admin"
        else:
            # If not admin, check the user table
            user = db.query(User).filter(User.email == user_info['email']).first()
            if user:
                role = user.role
            else:
                role = "analyst"  # Default fallback role if user not found

        # Step 4: Generate a JWT token with user info
        jwt_token = create_jwt_token(user_info)

        # Step 5: Frontend app URL to redirect to after successful login
        frontend_url = "http://localhost:5173/dashboard"  # Modify based on deployment

        # Step 6: Construct the redirect URL with token and role as query params
        redirect_url = f"{frontend_url}?access_token={jwt_token}&role={role}"

        # Step 7: Redirect to frontend with token and role
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth2 Authentication Failed: {str(e)}")

# ---------------------------- Route: Current Authenticated User ----------------------------

@router.get("/me")
async def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get current authenticated user's information based on the JWT token.
    Checks both User and Admin tables.
    """
    try:
        # Decode JWT token
        payload = verify_jwt_token(token)
        email = payload["sub"]

        # First try fetching from User table
        user = db.query(User).filter(User.email == email).first()
        if user:
            return {
                "email": user.email,
                "name": user.name,
                "role": user.role
            }

        # If not in User table, check Admin table
        admin = db.query(Admin).filter(Admin.email == email).first()
        if admin:
            return {
                "email": admin.email,
                "name": admin.name,
                "role": "admin"  # Hardcoded since admin role may not be stored
            }

        # Neither in User nor Admin table
        raise HTTPException(status_code=404, detail="User not found")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------------------- Route: Logout ----------------------------

@router.post("/logout")
async def logout():
    """
    Logout the user. Since JWT is stateless, this will simply remove the token from the client side.
    The frontend should delete the token from localStorage/sessionStorage.
    """
    return JSONResponse(content={
        "message": "Successfully logged out. Please delete the token from your client(frontend)."
    })
