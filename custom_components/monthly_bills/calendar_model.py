"""Calendar event data and range rules without Home Assistant dependencies."""
from datetime import date, datetime, time, timedelta

from .model import status_for


def bill_events(bills: dict[str, dict], today: date) -> list[dict]:
    """One all-day event per stored due date; no speculative future cycles."""
    events = []
    for bill_id, bill in bills.items():
        due = date.fromisoformat(bill["due_date"])
        amount = f'${bill["cost"]:,.2f}'
        # An auto-advanced Paid acknowledgement belongs to the previous cycle.
        due_bill = dict(bill)
        if bill.get("auto_advanced", False):
            due_bill["paid"] = False
        status = status_for(due_bill, today)
        description = (
            f'Bill: {bill["name"]}\n'
            f'Amount: {amount}\n'
            f'Due date: {due.isoformat()}\n'
            f'Status: {status}\n'
            f'Category: {bill.get("category", "Other")}\n'
            f'Autopay: {"Yes" if bill.get("autopay", False) else "No"}\n'
            f'Last payment: {bill.get("last_paid_on") or "Not recorded"}\n'
            f'Bill ID: {bill_id}'
        )
        events.append({
            "start": due,
            "end": due + timedelta(days=1),
            "summary": f'{bill["name"]} — {amount}',
            "description": description,
            "uid": f"monthly_bills_{bill_id}_{due.isoformat()}",
        })
    return sorted(events, key=lambda event: (event["start"], event["summary"], event["uid"]))


def events_between(events: list[dict], start: datetime, end: datetime) -> list[dict]:
    """Return overlap with an exclusive range, interpreting dates in local TZ."""
    if end <= start:
        return []
    return [
        event for event in events
        if datetime.combine(event["start"], time.min, tzinfo=start.tzinfo) < end
        and datetime.combine(event["end"], time.min, tzinfo=start.tzinfo) > start
    ]


def current_or_next(events: list[dict], today: date) -> dict | None:
    return next((event for event in events if event["end"] > today), None)
