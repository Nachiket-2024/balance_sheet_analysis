# Importing necessary classes from SQLAlchemy
from sqlalchemy import Column, Integer, String
from ..db.base import Base

class Vertical(Base):
    # The table name in the database
    __tablename__ = 'verticals'
    
    # Unique ID for the vertical (primary key)
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # The name of the vertical
    name = Column(String, nullable=False)
