from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..models.user_model import User  # Import the User model for database operations
from ..models.admin_model import Admin  # Import the Admin model for checking admin role
from ..db.session import get_db  # Import the get_db dependency to get the session

# Create FastAPI router for role-based routes
router = APIRouter()

# Route to get user role based on email (only accessible to admins)
@router.get("/user-role/{email}")
async def get_user_role(email: str, db: Session = Depends(get_db)):
    """
    Get the role of a user by their email. This route can only be accessed by admin users.
    """
    try:
        # Check if the requesting user is an admin first
        admin = db.query(Admin).filter(Admin.email == email).first()
        if not admin:
            raise HTTPException(status_code=403, detail="Insufficient privileges. Admin access required.")
        
        # Check if the user exists
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Return the user's role
        return {"email": user.email, "role": user.role}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

# Route to update user role (only accessible to admins)
@router.put("/update-role/{email}")
async def update_user_role(email: str, new_role: str, db: Session = Depends(get_db)):
    """
    Update the role of a user by email. This route can only be accessed by admin users.
    """
    try:
        # Check if the requesting user is an admin first
        admin = db.query(Admin).filter(Admin.email == email).first()
        if not admin:
            raise HTTPException(status_code=403, detail="Insufficient privileges. Admin access required.")

        # Check if the user exists
        user = db.query(User).filter(User.email == email).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Update the user's role
        user.role = new_role
        db.commit()
        db.refresh(user)

        return {"email": user.email, "role": user.role}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
