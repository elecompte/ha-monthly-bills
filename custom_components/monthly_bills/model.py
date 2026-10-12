"""Pure billing-cycle rules; dates are supplied in Home Assistant local time."""
from calendar import monthrange
from copy import deepcopy
from datetime import date

DEFAULT_THRESHOLD = 7


def checked_threshold(value) -> int:
    value = float(value)
    if not value.is_integer() or not 0 <= value <= 30:
        raise ValueError("Upcoming threshold must be a whole number from 0 to 30")
    return int(value)


def migrate_bill(bill: dict) -> dict:
    """Add fields without changing dates, identifiers, payments or history."""
    bill = deepcopy(bill)
    bill.setdefault("auto_advance_due_date", True)
    bill.setdefault("upcoming_threshold_days", DEFAULT_THRESHOLD)
    previous_paid = next((item.get("paid_on") for item in reversed(bill.get("history", []))
                          if item.get("paid_on")), None)
    bill.setdefault("last_paid_on", bill.get("paid_on") or previous_paid)
    bill.setdefault("last_payment_recorded_on", bill.get("last_paid_on"))
    bill.setdefault("last_paid_due_date", None)
    bill.setdefault("auto_advanced", False)
    bill.setdefault("due_day", date.fromisoformat(bill["due_date"]).day)
    return bill


def is_approaching(bill: dict, today: date) -> bool:
    return (date.fromisoformat(bill["due_date"]) - today).days <= bill["upcoming_threshold_days"]


def paid_for_display(bill: dict, today: date) -> bool:
    """Paid is an acknowledgement of the previous cycle after auto-advance."""
    return bill["paid"] and not (bill.get("auto_advanced", False) and is_approaching(bill, today))


def status_for(bill: dict, today: date | None = None) -> str:
    today = today or date.today()
    if paid_for_display(bill, today):
        return "Paid"
    due = date.fromisoformat(bill["due_date"])
    if due < today:
        return "Past Due"
    return "Due Today" if due == today else "Upcoming"


def next_due_date(bill: dict) -> str:
    old = date.fromisoformat(bill["due_date"])
    year, month = old.year, old.month + 1
    if month == 13:
        year, month = year + 1, 1
    return date(year, month, min(bill["due_day"], monthrange(year, month)[1])).isoformat()


def archive_payment(bill: dict) -> None:
    bill["history"] = (bill.get("history", []) + [{
        "due_date": bill["due_date"], "cost": bill["cost"],
        "payment_status": "Paid", "paid_on": bill["paid_on"],
    }])[-24:]


def refresh_bill(bill: dict, today: date) -> dict:
    bill = deepcopy(bill)
    if bill["paid"] and bill.get("auto_advanced", False) and is_approaching(bill, today):
        bill["paid"] = False
        bill["paid_on"] = None
    return bill


def record_payment(bill: dict, today: date, explicit: bool = False) -> dict:
    """Pay the displayed due cycle once; explicit permits early next payments."""
    bill = refresh_bill(bill, today)
    if bill["paid"] and not explicit:
        return bill
    # A late payment or long threshold can reopen immediately. Retry calls on
    # the same day must still not pay multiple cycles; use explicit early pay.
    if not explicit and bill.get("auto_advanced") and bill.get("last_payment_recorded_on", bill.get("last_paid_on")) == today.isoformat():
        return bill
    if bill.get("last_paid_due_date") == bill["due_date"]:
        return bill
    bill["paid"] = True
    bill["paid_on"] = today.isoformat()
    bill["last_paid_on"] = today.isoformat()
    bill["last_payment_recorded_on"] = today.isoformat()
    bill["last_paid_due_date"] = bill["due_date"]
    bill["auto_advanced"] = False
    if bill["auto_advance_due_date"]:
        archive_payment(bill)
        bill["due_date"] = next_due_date(bill)
        bill["auto_advanced"] = True
    return refresh_bill(bill, today)


def correct_last_payment_date(bill: dict, paid_on: date) -> dict:
    """Correct the latest payment, without opening or advancing a cycle."""
    bill = deepcopy(bill)
    # Retain the recording date for same-day retry protection when backdating.
    bill.setdefault("last_payment_recorded_on", bill.get("last_paid_on"))
    current_payment = (
        bill.get("paid_on") is not None
        and not bill.get("auto_advanced", False)
        and bill.get("last_paid_due_date") in (None, bill["due_date"])
    )
    if current_payment:
        bill["paid_on"] = paid_on.isoformat()
    else:
        history = bill.get("history", [])
        if not history or history[-1].get("payment_status") != "Paid":
            raise ValueError("No recorded payment to correct. Record a payment first.")
        latest = history[-1]
        # This editor targets the last archived payment explicitly. Legacy or
        # manually edited data may have a different last_paid_due_date marker;
        # that marker must not block correction or be changed by this action.
        latest["paid_on"] = paid_on.isoformat()
        # Paid acknowledgement may still refer to the just-archived payment.
        if bill.get("auto_advanced") and bill.get("paid_on") is not None:
            bill["paid_on"] = paid_on.isoformat()
    bill["last_paid_on"] = paid_on.isoformat()
    return bill


def reopen_bill(bill: dict) -> dict:
    """Reopen the displayed cycle; retain the payment audit history."""
    bill = deepcopy(bill)
    bill["paid"] = False
    bill["paid_on"] = None
    bill["auto_advanced"] = False
    if bill.get("last_paid_due_date") == bill["due_date"]:
        bill["last_paid_due_date"] = None
    return bill


def roll_bill(bill: dict) -> dict:
    """Manual advance only for a paid cycle that has not already advanced."""
    if not bill["paid"] or bill.get("auto_advanced", False):
        raise ValueError("Only a paid, unadvanced cycle can be rolled over.")
    bill = deepcopy(bill)
    archive_payment(bill)
    bill["last_paid_on"] = bill.get("paid_on") or bill.get("last_paid_on")
    bill["last_paid_due_date"] = bill["due_date"]
    bill["due_date"] = next_due_date(bill)
    bill["paid"] = False
    bill["paid_on"] = None
    return bill
