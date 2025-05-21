from datetime import datetime

from pydantic import BaseModel, ConfigDict


class InventoryLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    quantity_change: int
    reason: str
    created_at: datetime
