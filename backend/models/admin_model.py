# Importing required classes and modules from SQLAlchemy
from sqlalchemy import Column, Integer, String
from ..db.base import Base  # Importing the Base class to inherit from

class Admin(Base):
    """
    Admin model represents the administrators for the system.
    Admin users have global access to the entire system.
    """
    
    # Table name in the database
    __tablename__ = 'admins'
    
    # Primary key for each admin record
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Name of the admin user
    name = Column(String, nullable=False)
    
    # Unique email for identifying the admin user
    email = Column(String, unique=True, nullable=False)
