import os
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from fastapi import Request
from dotenv import load_dotenv
from jose import JWTError, jwt
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

# OAuth2 route to handle the redirect from Google after successful authentication
@router.get("/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """
    Handle the Google OAuth2 callback and exchange the authorization code for a JWT token.
    """
    try:
        # Use the authorization code to authenticate the user and fetch user info
        user_info = authenticate_with_google(code, db)

        # Check if the user is an admin by looking up their email in the Admin table
        admin = db.query(Admin).filter(Admin.email == user_info['email']).first()

        # Assign role as 'admin' only if found in Admin table, otherwise check in User table
        if admin:
            role = "admin"
        else:
            # Check if the user already exists in the User table
            user = db.query(User).filter(User.email == user_info['email']).first()

            if not user:
                # If the user doesn't exist, assign as "analyst" by default
                role = "analyst"
                # Create the user with default role
                new_user = User(
                    name=user_info['name'],
                    email=user_info['email'],
                    role=role,
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                user = new_user  # Use the newly created user
            else:
                role = user.role  # Only use the role stored in the database, without any default

        # Create a JWT token with user info and role
        jwt_token = create_jwt_token(user_info)

        # Return the JWT token and the user's role in the response
        return JSONResponse(content={"access_token": jwt_token, "token_type": "bearer", "role": role})

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Google OAuth2 Authentication Failed: {str(e)}")

# Route to get current user info (protected)
@router.get("/me")
async def read_users_me(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Get current authenticated user's information based on the JWT token.
    """
    try:
        payload = verify_jwt_token(token)
        user = db.query(User).filter(User.email == payload["sub"]).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"email": user.email, "name": user.name, "role": user.role}

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
