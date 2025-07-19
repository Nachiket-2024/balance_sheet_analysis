# Importing necessary classes from Pydantic
from pydantic import BaseModel, ConfigDict

# Pydantic schema for reading company data
class CompanyBase(BaseModel):
    # The name of the company (required)
    name: str

    # Parent company ID (nullable, can be None for top-level companies)
    parent_company_id: int = None

    # Pydantic's method to convert the model into a dictionary (optional)
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects

# Schema for creating a new company
class CompanyCreate(CompanyBase):
    # You can add any additional fields for company creation here
    pass

# Schema for returning company data (read-only, might exclude sensitive fields)
class CompanyResponse(CompanyBase):
    # Adding the ID field to the response schema
    id: int

    # Pydantic's method to convert the model into a dictionary (optional)
    class Config(ConfigDict):
        from_attributes = True  # Enables compatibility with ORM objects
