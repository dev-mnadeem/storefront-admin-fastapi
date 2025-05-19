from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A bounded slice of a collection plus the total the slice came from."""

    items: list[T]
    total: int
    limit: int
    offset: int


class HealthStatus(BaseModel):
    status: str
    database: str
    version: str
