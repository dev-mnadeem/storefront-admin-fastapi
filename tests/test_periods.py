from datetime import date

import pytest
from sqlalchemy import func

from app.core.errors import InvalidRequestError
from app.models.sales import Sale
from app.repositories.periods import (
    INTERVALS,
    period_bounds,
    period_expression,
    register_dialect,
    supported_dialects,
)


@pytest.mark.parametrize(
    ("interval", "expected"),
    [
        ("day", (date(2025, 5, 19), date(2025, 5, 18), date(2025, 5, 18))),
        ("week", (date(2025, 5, 19), date(2025, 5, 12), date(2025, 5, 18))),
        ("month", (date(2025, 5, 1), date(2025, 4, 1), date(2025, 4, 30))),
        ("year", (date(2025, 1, 1), date(2024, 1, 1), date(2024, 12, 31))),
    ],
)
def test_period_bounds(interval: str, expected: tuple[date, date, date]) -> None:
    assert period_bounds(interval, date(2025, 5, 19)) == expected


def test_period_bounds_rejects_unknown_interval() -> None:
    with pytest.raises(InvalidRequestError):
        period_bounds("fortnight", date(2025, 5, 19))


@pytest.mark.parametrize("dialect", ["sqlite", "mysql", "postgresql"])
@pytest.mark.parametrize("interval", INTERVALS)
def test_every_dialect_covers_every_interval(dialect: str, interval: str) -> None:
    assert period_expression(dialect, interval, Sale.sale_date) is not None


def test_unregistered_dialect_is_reported() -> None:
    with pytest.raises(InvalidRequestError) as raised:
        period_expression("oracle", "month", Sale.sale_date)
    assert "oracle" in raised.value.message


def test_register_dialect_requires_every_interval() -> None:
    with pytest.raises(ValueError):
        register_dialect("partial", {"day": func.date})


def test_register_dialect_adds_a_backend() -> None:
    register_dialect("duckdb", dict.fromkeys(INTERVALS, func.date))
    assert "duckdb" in supported_dialects()
    assert period_expression("duckdb", "week", Sale.sale_date) is not None
