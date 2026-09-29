"""Small pure-Python functions for bill periods and payment status."""

from calendar import monthrange
from datetime import date


def status_for(bill: dict, today: date | None = None) -> str:
    """Unpaid bills stay overdue until explicitly paid or changed."""
    today = today or date.today()
    if bill["paid"]:
        return "Paid"
    return "Past Due" if date.fromisoformat(bill["due_date"]) < today else "Upcoming"


def next_due_date(bill: dict) -> str:
    """Maintain the original day-of-month across short months."""
    old = date.fromisoformat(bill["due_date"])
    year, month = old.year, old.month + 1
    if month == 13:
        year, month = year + 1, 1
    day = min(bill["due_day"], monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def roll_bill(bill: dict) -> dict:
    """Archive one occurrence and initialize the next one. Caller must check paid."""
    previous = {
        "due_date": bill["due_date"],
        "cost": bill["cost"],
        "payment_status": "Paid" if bill["paid"] else "Past Due",
        "paid_on": bill["paid_on"],
    }
    updated = dict(bill)
    updated["history"] = (bill.get("history", []) + [previous])[-24:]
    updated["due_date"] = next_due_date(bill)
    updated["paid"] = False
    updated["paid_on"] = None
    return updated
