import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from dotenv import load_dotenv
from sqlalchemy.orm import Session
import requests

from .auth_user_info import get_google_user_info
from ..models.user_model import User
from ..models.admin_model import Admin

# Load environment variables from the .env file
load_dotenv()

# Get JWT Secret Key and OAuth Configuration from environment variables
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_SCOPES = os.getenv("GOOGLE_SCOPES").split(",")  # Ensure it's a list of scopes
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

if not JWT_SECRET or not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET or not GOOGLE_REDIRECT_URI:
    raise ValueError("Missing required environment variables")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

# Helper function to create JWT token
def create_jwt_token(user_info):
    """Create JWT token for the authenticated user."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {
        "sub": user_info["email"],  # User's email
        "role": user_info["role"],  # User's role (e.g., Admin, Analyst)
        "exp": expire  # Token expiration
    }
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return encoded_jwt

# Helper function to verify JWT token
def verify_jwt_token(token: str):
    """Verify and decode the JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload  # Returns the decoded JWT payload
    except JWTError:
        raise Exception("Could not validate credentials")

# Helper function to authenticate the user using Google OAuth2
def authenticate_with_google(code: str, db: Session):
    try:
        # Step 1: Exchange authorization code for access token
        token_data = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        response = requests.post("https://oauth2.googleapis.com/token", data=token_data)
        response.raise_for_status()  # Raise an exception for 4xx/5xx responses
        token_info = response.json()

        # Check if the token is available
        if "access_token" not in token_info:
            raise Exception("Failed to obtain access token from Google")

        access_token = token_info["access_token"]

        # Step 2: Fetch user info using the Google OAuth2 user info endpoint
        user_info_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo", 
            headers={"Authorization": f"Bearer {access_token}"}
        )
        user_info_response.raise_for_status()
        user_info = user_info_response.json()

        # Print the fetched user info for debugging purposes
        print("User info fetched from Google:", user_info)

        # Extract the name and email from the response
        user_name = user_info.get("name", "")
        user_email = user_info.get("email", "")

        # Initialize the role variable (to avoid errors)
        role = "analyst"  # Default role

        # Step 3: Check if the user exists in the Admin table
        admin = db.query(Admin).filter(Admin.email == user_email).first()

        if admin:
            # If the user is found in the Admin table, assign role as 'admin'
            role = "admin"
        else:
            # If the user is not found in Admin table, check in the User table
            user = db.query(User).filter(User.email == user_email).first()

            if not user:
                # If the user doesn't exist, assign 'analyst' as default role and create the user
                user = User(
                    name=user_name,
                    email=user_email,
                    role=role,  # Use the role assigned earlier (analyst)
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"New user created: {user.name} ({user.email})")
            else:
                # If user exists, use the role already in the database
                role = user.role

        # Return the user info (e.g., for JWT creation)
        return {"email": user_email, "name": user_name, "role": role}

    except Exception as e:
        print(f"Error: {str(e)}")  # Print out the error if any
        raise Exception(f"Error during Google authentication: {str(e)}")
