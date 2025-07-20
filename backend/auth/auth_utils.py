# Standard library imports
import os
from datetime import datetime, timedelta, timezone

# JWT handling
from jose import JWTError, jwt

# Load environment variables from .env file
from dotenv import load_dotenv

# ORM handling
from sqlalchemy.orm import Session

# To make HTTP requests to Google OAuth endpoints
import requests

# Import user and admin models
from ..models.user_model import User
from ..models.admin_model import Admin

# ---------------------------- Load Environment Variables ----------------------------

# Load the .env file
load_dotenv()

# Required OAuth and JWT configuration from environment
JWT_SECRET = os.getenv("JWT_SECRET")  # Secret key used to encode/decode JWT
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")  # Algorithm for encoding JWT (e.g., HS256)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")  # Client ID from Google Console
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")  # Secret from Google Console
GOOGLE_SCOPES = os.getenv("GOOGLE_SCOPES").split(",")  # OAuth scopes as a list
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")  # Redirect URI registered in Google Console

# Check that all required environment variables are present
if not JWT_SECRET or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
    raise ValueError("Missing required environment variables")

# Set JWT expiration (defaults to 60 minutes if not set)
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# ---------------------------- Create JWT Token ----------------------------

def create_jwt_token(user_info):
    """
    Create JWT token for the authenticated user.
    """
    # Set token expiration time
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # Payload to be encoded into JWT
    to_encode = {
        "sub": user_info["email"],  # Subject: user's email
        "role": user_info["role"],  # Custom claim: user role
        "exp": expire               # Expiration time
    }

    # Encode and return the JWT token
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

# ---------------------------- Verify JWT Token ----------------------------

def verify_jwt_token(token: str):
    """
    Verify and decode the JWT token.
    """
    try:
        # Decode JWT using secret and algorithm
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload  # Returns the decoded token content
    except JWTError:
        # Raise error if decoding fails
        raise Exception("Could not validate credentials")

# ---------------------------- Google OAuth2 Authentication ----------------------------

def authenticate_with_google(code: str, db: Session):
    """
    Authenticate the user using Google OAuth2.
    - Exchanges code for access token
    - Fetches user info from Google
    - Creates user in DB if not found
    - Returns user info with role
    """
    try:
        # -------- Step 1: Exchange authorization code for access token --------
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",  # Required grant type
        }

        # Make POST request to Google's token endpoint
        response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
        response.raise_for_status()  # Raise error for bad status codes
        token_info = response.json()  # Parse response as JSON

        # Validate access token exists in response
        if "access_token" not in token_info:
            raise Exception("Failed to obtain access token from Google")

        access_token = token_info["access_token"]

        # -------- Step 2: Use access token to get user info from Google --------
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo", 
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info_response.raise_for_status()  # Raise if unauthorized or error
        user_info = user_info_response.json()  # Extract user info

        # Debug print for verification
        print("User info fetched from Google:", user_info)

        # Extract necessary user fields
        user_name = user_info.get("name", "")
        user_email = user_info.get("email", "")

        # Default role
        role = "analyst"

        # -------- Step 3: Role assignment and DB registration --------

        # Check if user is an admin
        admin = db.query(Admin).filter(Admin.email == user_email).first()
        if admin:
            role = "admin"
        else:
            # Check if user already exists
            user = db.query(User).filter(User.email == user_email).first()

            if not user:
                # Create a new user with default role (analyst)
                user = User(
                    name=user_name,
                    email=user_email,
                    role=role
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"New user created: {user.name} ({user.email})")
            else:
                # Use role from DB if user exists
                role = user.role

        # Return dictionary of user data for JWT token generation
        return {"email": user_email, "name": user_name, "role": role}

    except Exception as e:
        # Log and raise any exceptions
        print(f"Error: {str(e)}")
        raise Exception(f"Error during Google authentication: {str(e)}")
