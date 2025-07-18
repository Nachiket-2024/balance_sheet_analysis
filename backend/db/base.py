# Import DeclarativeBase from SQLAlchemy's ORM package.
# DeclarativeBase is the recommended base class in SQLAlchemy 2.0+
# for defining declarative model classes (i.e., database tables).
from sqlalchemy.orm import DeclarativeBase


# Define a base class for all ORM models in the application.
# All model classes (e.g., User, Taal, Raag) will inherit from this `Base` class.
# This gives SQLAlchemy the metadata and functionality it needs to map models to tables.
class Base(DeclarativeBase):
    pass  # No extra customization is needed here—just inherit from DeclarativeBase
