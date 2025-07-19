# Importing necessary classes from SQLAlchemy
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from ..db.base import Base

class Company(Base):
    # The table name in the database
    __tablename__ = 'companies'
    
    # Unique ID for the company (primary key)
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Parent company ID (foreign key that points to the same table)
    parent_company_id = Column(Integer, ForeignKey('companies.id'), nullable=True)
    
    # The name of the company
    name = Column(String, nullable=False)
    
    # Relationship for getting the parent company (optional)
    parent_company = relationship("Company", remote_side=[id], backref="subsidiaries")
