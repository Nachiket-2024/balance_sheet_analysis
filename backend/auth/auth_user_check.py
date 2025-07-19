from fastapi import HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError  # Importing JWTError for exception handling

from ..db.session import get_db
from .auth_utils import verify_jwt_token  # Assuming verify_jwt_token handles the decoding of the JWT
from ..models.admin_model import Admin  # Import Admin model to query admin table

# Initialize the OAuth2PasswordBearer scheme to extract token from headers
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Dependency to check if the user is an admin
def admin_only(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        # Decode the JWT token and get the payload (which contains the user's email)
        payload = verify_jwt_token(token)
        user_email = payload.get("sub")  # This is the user's email from the JWT token

        # Check if the user exists in the Admin table
        admin = db.query(Admin).filter(Admin.email == user_email).first()
        
        # If no admin entry exists, raise an exception
        if not admin:
            raise HTTPException(status_code=403, detail="Admin access required")

        return admin  # Optionally return the admin entry if you need it

    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
