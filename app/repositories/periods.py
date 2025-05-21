"""Calendar bucketing, per SQL dialect.

The revenue endpoints group sales by day/week/month/year. There is no
portable SQL for that, so each dialect registers its own expression builders
here instead of hard-coding MySQL functions inside a query. Adding another
backend means calling :func:`register_dialect` - nothing else changes.
"""

from collections.abc import Callable
from datetime import date, timedelta
from typing import Literal, get_args

from sqlalchemy import ColumnElement, func

from app.core.errors import InvalidRequestError

IntervalName = Literal["day", "week", "month", "year"]
Interval = str
PeriodExpression = Callable[[ColumnElement], ColumnElement]

INTERVALS: tuple[str, ...] = get_args(IntervalName)

_REGISTRY: dict[str, dict[Interval, PeriodExpression]] = {
    "sqlite": {
        "day": lambda c: func.strftime("%Y-%m-%d", c),
        "week": lambda c: func.strftime("%Y-W%W", c),
        "month": lambda c: func.strftime("%Y-%m", c),
        "year": lambda c: func.strftime("%Y", c),
    },
    "mysql": {
        "day": lambda c: func.date_format(c, "%Y-%m-%d"),
        "week": lambda c: func.date_format(c, "%Y-W%u"),
        "month": lambda c: func.date_format(c, "%Y-%m"),
        "year": lambda c: func.date_format(c, "%Y"),
    },
    "postgresql": {
        "day": lambda c: func.to_char(c, "YYYY-MM-DD"),
        "week": lambda c: func.to_char(c, 'YYYY-"W"IW'),
        "month": lambda c: func.to_char(c, "YYYY-MM"),
        "year": lambda c: func.to_char(c, "YYYY"),
    },
}


def register_dialect(name: str, builders: dict[Interval, PeriodExpression]) -> None:
    """Teach the analytics queries about another database."""
    missing = set(INTERVALS) - set(builders)
    if missing:
        raise ValueError(f"dialect {name!r} is missing intervals: {sorted(missing)}")
    _REGISTRY[name] = dict(builders)


def supported_dialects() -> tuple[str, ...]:
    return tuple(sorted(_REGISTRY))


def period_expression(dialect: str, interval: Interval, column: ColumnElement):
    """Return the SQL expression that labels ``column`` with its period."""
    if interval not in INTERVALS:
        raise InvalidRequestError(
            f"Unknown interval {interval!r}.", supported=list(INTERVALS)
        )
    builders = _REGISTRY.get(dialect)
    if builders is None:
        raise InvalidRequestError(
            f"No period expressions registered for SQL dialect {dialect!r}.",
            supported=list(supported_dialects()),
        )
    return builders[interval](column)


def period_bounds(interval: Interval, today: date) -> tuple[date, date, date]:
    """Return ``(current_start, previous_start, previous_end)`` for ``today``."""
    if interval == "day":
        current_start = today
    elif interval == "week":
        current_start = today - timedelta(days=today.weekday())
    elif interval == "month":
        current_start = today.replace(day=1)
    elif interval == "year":
        current_start = today.replace(month=1, day=1)
    else:
        raise InvalidRequestError(
            f"Unknown interval {interval!r}.", supported=list(INTERVALS)
        )

    previous_end = current_start - timedelta(days=1)
    if interval == "day":
        previous_start = previous_end
    elif interval == "week":
        previous_start = current_start - timedelta(weeks=1)
    elif interval == "month":
        previous_start = previous_end.replace(day=1)
    else:
        previous_start = current_start.replace(year=current_start.year - 1)

    return current_start, previous_start, previous_end
