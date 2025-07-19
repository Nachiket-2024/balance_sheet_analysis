import os
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow

from .auth_user_info import get_google_user_info
from ..models.user_model import User

# Load environment variables from the .env file
load_dotenv()

# Get JWT Secret Key and OAuth Configuration from environment variables
JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_SCOPES = os.getenv("GOOGLE_SCOPES").split(",")
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
        # Debugging: Print out the environment variables to ensure they are loaded correctly
        print("Google Client ID:", os.getenv("GOOGLE_CLIENT_ID"))
        print("Google Client Secret:", os.getenv("GOOGLE_CLIENT_SECRET"))
        print("Google Redirect URI:", os.getenv("GOOGLE_REDIRECT_URI"))
        print("Google Scopes:", os.getenv("GOOGLE_SCOPES"))

        # Initialize Google OAuth2 flow
        flow = Flow.from_client_config(
            client_config={ 
                "web": {
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "redirect_uris": [GOOGLE_REDIRECT_URI]
                }
            },
            scopes=GOOGLE_SCOPES
        )
        
        # Ensure the full URL is passed, not just the code
        authorization_response = f"{GOOGLE_REDIRECT_URI}?code={code}"
        
        # Exchange code for token
        flow.fetch_token(
            authorization_response=authorization_response,  # Full URL with the authorization code
            client_secret=GOOGLE_CLIENT_SECRET,
        )

        if not flow.credentials:
            raise Exception("Failed to get Google credentials")
        
        # Now use the access token to fetch the user info
        credentials = flow.credentials
        user_info = get_google_user_info(credentials)
        
        # Check if the user exists in the DB
        user = db.query(User).filter(User.email == user_info["email"]).first()
        if not user:
            # Create new user if not found
            user = User(
                name=user_info.get("name", ""),
                email=user_info["email"],
                role="analyst",  # default role
            )
            db.add(user)
            db.commit()
            db.refresh(user)

        return user_info
    except Exception as e:
        raise Exception(f"Error during Google authentication: {str(e)}")
