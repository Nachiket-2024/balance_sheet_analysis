# Importing necessary classes from Pydantic
from pydantic import BaseModel, ConfigDict

# Base Pydantic model for Admin data (common fields)
class AdminBase(BaseModel):
    name: str
    email: str

    # Pydantic configuration to enable compatibility with ORM objects
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects

# Schema for creating a new admin (used when creating an admin via an API)
class AdminCreate(AdminBase):
    pass

# Schema for returning admin details (used when sending data back to the client)
class AdminRead(AdminBase):
    id: int  # Adding the ID field, as it's returned in the response

    # Pydantic configuration to enable compatibility with ORM objects
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects
