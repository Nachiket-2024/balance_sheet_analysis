# Importing necessary classes from Pydantic
from pydantic import BaseModel, EmailStr, ConfigDict

# Pydantic schema for reading user data
class UserBase(BaseModel):
    # User's name (required)
    name: str
    
    # User's email (must be a valid email format)
    email: EmailStr
    
    # User's role (e.g., 'admin', 'analyst', 'ceo')
    role: str

    # Pydantic's method to convert the model into a dictionary (optional)
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects

# Schema for creating a new user
class UserCreate(UserBase):
    # Additional fields for creating a user can be added here (currently inheriting UserBase)
    pass

# Schema for returning user data (read-only, might exclude sensitive fields)
class UserResponse(UserBase):
    id: int  # Adding the ID field, as it's returned in the response

    # Pydantic's method to convert the model into a dictionary (optional)
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects
