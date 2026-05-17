""" "What you owe this month" — recomputed on read, not a ledger (D16). Each
billable agent is charged the prorated amount if it started this calendar month,
else the full monthly price; referral credit is then applied (floored at 0)."""

from __future__ import annotations

from calendar import monthrange
from dataclasses import dataclass
from datetime import date

from backend.db.models import Agent
from backend.services.proration import first_period_cents

# Rented & running this month (recycled/pending are not charged).
BILLABLE = {"deployed", "stopped", "paid", "canceling", "error"}


@dataclass(slots=True)
class UsageLine:
    agent_id: str
    display_name: str
    days_charged: int
    amount_cents: int


@dataclass(slots=True)
class Usage:
    month: str  # YYYY-MM
    items: list[UsageLine]
    subtotal_cents: int
    credit_cents: int
    total_cents: int


def compute_usage(agents: list[Agent], credit_cents: int, today: date) -> Usage:
    days_in_month = monthrange(today.year, today.month)[1]
    items: list[UsageLine] = []
    subtotal = 0
    for a in agents:
        if a.status not in BILLABLE:
            continue
        start = a.billing_period_start or a.created_at.date()
        if start.year == today.year and start.month == today.month:
            amount = first_period_cents(a.monthly_cost_cents, start)
            days = days_in_month - start.day + 1
        else:  # started before this month → full month
            amount = a.monthly_cost_cents
            days = days_in_month
        subtotal += amount
        items.append(UsageLine(a.id, a.display_name, days, amount))

    applied_credit = min(credit_cents, subtotal)
    return Usage(
        month=f"{today.year:04d}-{today.month:02d}",
        items=items,
        subtotal_cents=subtotal,
        credit_cents=applied_credit,
        total_cents=subtotal - applied_credit,
    )
