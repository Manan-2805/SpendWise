# Import all models to ensure they register with Base.metadata.
# Alembic imports this module, which triggers all model registrations.
# Without these imports, Alembic cannot detect new or changed tables.

from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User

# Re-export for convenience — other modules can do:
# from app.models import User, Category, Transaction
__all__: list[str] = ["User", "Category", "Transaction"]
