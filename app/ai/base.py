from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.schemas.insights import InsightMetrics


@dataclass(frozen=True)
class ProviderResult:
    headline: str
    bullets: list[str]


@runtime_checkable
class InsightProvider(Protocol):
    """Turns a bundle of measured figures into prose for the dashboard."""

    name: str

    async def write(self, metrics: InsightMetrics) -> ProviderResult: ...
