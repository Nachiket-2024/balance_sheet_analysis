# Importing necessary SQLAlchemy classes
from sqlalchemy import Column, Integer, String
# Importing Base class from the db.base module
from ..db.base import Base

class User(Base):
    # The table name in the database
    __tablename__ = 'users'
    
    # Unique ID for the user (primary key)
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User's name (cannot be null)
    name = Column(String, nullable=False)
    
    # User's email (must be unique, cannot be null)
    email = Column(String, unique=True, nullable=False)
    
    # User's role (could be 'admin', 'analyst', 'ceo', etc.)
    role = Column(String, default="analyst", nullable=False)  # Default role is 'analyst'
