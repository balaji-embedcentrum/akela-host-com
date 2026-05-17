"""Calendar-day proration (D15). The first calendar month is charged only for
the days from the rent date through month-end; renting on the 1st = full month."""

from __future__ import annotations

from calendar import monthrange
from datetime import date


def first_period_cents(monthly_cents: int, on: date) -> int:
    days_in_month = monthrange(on.year, on.month)[1]
    remaining = days_in_month - on.day + 1  # rent day .. last day, inclusive
    if remaining >= days_in_month:  # rented on the 1st → full month
        return monthly_cents
    return round(monthly_cents * remaining / days_in_month)
