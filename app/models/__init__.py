"""SQLAlchemy models.

Importing this package registers every table on ``Base.metadata``, which is
what ``create_all`` and the test fixtures rely on.
"""

from app.models.inventory import Inventory
from app.models.inventory_log import InventoryLog
from app.models.products import Product
from app.models.sales import Sale

__all__ = ["Inventory", "InventoryLog", "Product", "Sale"]
