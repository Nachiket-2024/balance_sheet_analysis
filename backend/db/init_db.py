# Import the SQLAlchemy engine instance used to connect to the database.
# This engine is responsible for issuing SQL commands and transactions.
from .session import engine

# Import the base metadata class from your declarative base definition.
# It holds information about all table models defined using SQLAlchemy ORM.
from .base import Base

# Import the User model class for the same reason — it must be registered to create its table.
from ..models.user_model import User
from ..models.company_model import Company
from ..models.vertical_model import Vertical
from ..models.balance_sheet_model import BalanceSheet


def init_db() -> None:
    """
    Initializes the database schema by creating all registered tables.

    - `Base.metadata.create_all(...)` reads all model classes attached to the `Base`
      and creates the corresponding tables in the database.
    - `bind=engine` tells SQLAlchemy which DB connection to use.
    - This is typically used only for initial development or testing — in production,
      you'd usually use Alembic migrations instead.
    """
    Base.metadata.create_all(bind=engine)


# This allows running the script directly (e.g., `python db/init_db.py`) to initialize the DB.
# When the file is executed as a standalone script, it calls `init_db()` to create tables.
if __name__ == "__main__":
    init_db()
