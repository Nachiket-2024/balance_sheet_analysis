# Importing necessary classes from Pydantic
from pydantic import BaseModel, ConfigDict

# Pydantic schema for reading vertical data
class VerticalBase(BaseModel):
    # The name of the vertical (required)
    name: str

    # Pydantic's method to convert the model into a dictionary (optional)
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects

# Schema for creating a new vertical
class VerticalCreate(VerticalBase):
    # You can add any additional fields for creating a vertical here (currently inheriting VerticalBase)
    pass

# Schema for returning vertical data (read-only, might exclude sensitive fields)
class VerticalResponse(VerticalBase):
    # Adding the ID field to the response schema
    id: int

    # Pydantic's method to convert the model into a dictionary (optional)
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects
