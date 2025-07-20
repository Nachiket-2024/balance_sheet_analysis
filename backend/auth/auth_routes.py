import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Request
from dotenv import load_dotenv
from jose import JWTError
from fastapi.security import OAuth2PasswordBearer

from .auth_utils import authenticate_with_google, create_jwt_token, verify_jwt_token
from ..models.user_model import User
from ..models.admin_model import Admin
from ..db.session import get_db

# Load environment variables from the .env file
load_dotenv()

# OAuth2PasswordBearer is used to extract the token from Authorization header
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Create FastAPI router for authentication related routes
router = APIRouter(
    prefix="/auth",  # Prefix for all authentication-related routes
    tags=["Authentication"],  # Tags to categorize the routes in the docs
)

# OAuth2 route for login via Google
@router.get("/login")
async def login_with_google(request: Request, db: Session = Depends(get_db)):
    """
    Initiates the Google OAuth2 flow.
    Redirects the user to the Google authentication page.
    """
    try:
        google_oauth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        # Build the URL to redirect the user to Google's OAuth2 authorization endpoint
        auth_url = f"{google_oauth_url}?response_type=code&client_id={os.getenv('GOOGLE_CLIENT_ID')}&redirect_uri={os.getenv('GOOGLE_REDIRECT_URI')}&scope=openid%20email"
        return RedirectResponse(url=auth_url)  # Redirect user to Google's OAuth2 page
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth2 Authentication Failed: {str(e)}")

# Callback route for Google OAuth2
@router.get("/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle the Google OAuth2 callback and exchange the authorization code for a JWT token.
    """
    try:
        # Step 1: Use the authorization code to authenticate the user and fetch user info
        user_info = authenticate_with_google(code, db)

        # Step 2: Check if the user is an admin by looking up their email in the Admin table
        admin = db.query(Admin).filter(Admin.email == user_info['email']).first()

        # Step 3: Assign role as 'admin' if found in Admin table, otherwise check in User table
        if admin:
            role = "admin"
        else:
            # Check if the user exists in the User table
            user = db.query(User).filter(User.email == user_info['email']).first()
            if user:
                role = user.role  # Use the role stored in the database
            else:
                role = "analyst"  # Default to analyst if the user is not found

        # Step 4: Create a JWT token with user info and role
        jwt_token = create_jwt_token(user_info)

        # Step 5: Define your frontend URL
        frontend_url = "http://localhost:5173/dashboard"  # Replace with your actual frontend URL

        # Step 6: Redirect the user to the frontend with JWT token and role as query parameters
        redirect_url = f"{frontend_url}?access_token={jwt_token}&role={role}"

        # Debugging: Print out the constructed redirect URL to verify it's correct
        print(f"Redirecting to: {redirect_url}")

        # Step 7: Return a RedirectResponse to the frontend URL
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth2 Authentication Failed: {str(e)}")


# Route to get current user info (protected)
@router.get("/me")
async def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get current authenticated user's information based on the JWT token.
    Checks both User and Admin tables.
    """
    try:
        # Decode token and extract email
        payload = verify_jwt_token(token)
        email = payload["sub"]

        # Check in User table first
        user = db.query(User).filter(User.email == email).first()
        if user:
            return {
                "email": user.email,
                "name": user.name,
                "role": user.role
            }

        # If not found in User, check in Admin table
        admin = db.query(Admin).filter(Admin.email == email).first()
        if admin:
            return {
                "email": admin.email,
                "name": admin.name,
                "role": "admin"  # Hardcoded since Admin table may not have role column
            }

        # If not found in either table
        raise HTTPException(status_code=404, detail="User not found")

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Route for user logout (client-side action, token invalidation)
@router.post("/logout")
async def logout():
    """
    Logout the user. Since JWT is stateless, this will simply remove the token from the client side.
    The frontend should delete the token from localStorage/sessionStorage.
    """
    return JSONResponse(content={"message": "Successfully logged out. Please delete the token from your client(frontend)."})
