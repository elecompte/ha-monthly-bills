# Monthly Bills for Home Assistant — v0.3.0

A local, editable monthly bill tracker. This release upgrades the v0.2.3 source and retains the storage key, bill IDs, device identifiers, and all existing entity unique IDs.

## Upgrade

1. Back up `/config/custom_components/monthly_bills/` and `/config/.storage/monthly_bills.data` (or make a full Home Assistant backup).
2. Extract this archive. Replace `/config/custom_components/monthly_bills/` with the archive's `custom_components/monthly_bills/` folder. Do not nest another `monthly_bills` directory inside it.
3. Restart Home Assistant. Keep the existing Monthly Bills integration configured; do not delete and re-add it.
4. Open a bill under Settings → Devices & Services → Monthly Bills → Devices. The new settings appear under Configuration.
5. Check Settings → System → Logs, then test with a temporary bill before marking real bills paid.

Existing dashboard entity IDs remain intact. New IDs depend on the device name and registry; a Rent device normally gets `switch.rent_auto_advance`, `number.rent_upcoming_threshold`, and `sensor.rent_last_paid`.

## New controls

| Control | Default | Behavior |
| --- | --- | --- |
| Auto advance | On | Recording payment advances the displayed due date by one month. |
| Upcoming threshold | 7 days | Range 0–30, whole days. Reopens an auto-advanced bill when its next due date is this many days away or closer. |
| Last paid | No date until payment | Preserves the last payment date after the bill becomes Upcoming. |

Both settings are available when adding a bill, as native entities for existing bills, and through `monthly_bills.add_bill` / `monthly_bills.update_bill` fields `auto_advance_due_date` and `upcoming_threshold_days`.

## Payment cycle

For a bill due October 1 with the default threshold:

- Mark it paid on October 1: due date becomes November 1, status Paid, Paid switch on.
- October 25: status Upcoming and Paid switch off.
- November 1: Due Today.
- November 2: Past Due if unpaid.

The integration refreshes at local midnight (five seconds after midnight) and at startup, and immediately after setting changes. Sensors and the switch also compute the current status using Home Assistant's local date. A threshold of 0 reopens on the due date. Threshold changes apply immediately; increasing it can reopen a bill. Once reopened, reducing it does not mark the bill paid again.

With auto advance disabled, payment leaves the date unchanged and status Paid indefinitely. The old midnight rollover is removed. Set a different due date, mark unpaid, or use manual rollover to reopen. Changing the auto-advance setting does not itself advance or reverse dates; an already advanced bill still reopens at its upcoming threshold.

Monthly advancement uses the original billing day: January 31 → February 28 (29 in leap years) → March 31. Editing the due date resets the billing day. Late payments advance exactly one month from the displayed due date, so a bill several months behind may remain Past Due after one payment.

## Actions and early payments

All existing actions remain: `add_bill`, `update_bill`, `mark_paid`, `mark_unpaid`, `rollover`, `delete_bill`.

- `mark_paid` / turning the Paid switch on records payment once while it is already acknowledged. Same-day retry calls are ignored even when a late payment immediately reopens the next cycle.
- `mark_unpaid` / turning the Paid switch off reopens the displayed cycle. It does not undo a date advancement or erase recorded history.
- `rollover` manually advances a paid cycle that has not already auto-advanced. It rejects unpaid and already advanced cycles to prevent double advancement.
- New `pay_next_cycle` explicitly records another payment for the displayed due date while Paid refers to the previous cycle. Use this for early payment before the upcoming threshold. This is an intentional payment action: each call can pay another month, so do not use it for retries or repeated refreshes.

Example: after October's payment advances Rent to November 1, pay November early on October 20:

```yaml
action: monthly_bills.pay_next_cycle
data:
  bill_id: rent
```

The due date becomes December 1 and status stays Paid until November 24.

Example settings update:

```yaml
action: monthly_bills.update_bill
data:
  bill_id: rent
  auto_advance_due_date: true
  upcoming_threshold_days: 7
```

## Data and migration

Storage remains `.storage/monthly_bills.data` with storage version 1. New fields are added without changing existing dates or payments. Already-paid records from v0.2.3 remain Paid until manually reopened or rolled over; installation does not treat them as a new payment. Last Paid initializes from the current `paid_on` or the latest recorded payment in history when available.

Auto-advanced payments are immediately archived against the paid due date, including amount and payment date. The existing history limit of 24 occurrences is retained. Auto-advance-disabled payments remain on the current record and are archived by manual rollover. Payment history survives automatic transition to Upcoming.

## HACS

The archive includes a repository-ready `custom_components/monthly_bills/` layout and `hacs.json`. Manual installation works directly. For HACS distribution, publish these files at a GitHub repository root, replace the manifest documentation URL with that repository's documentation URL, and create a v0.3.0 release. Add that repository as a HACS custom repository of type Integration. No GitHub release has been published by generating this archive.

## Validation

Run `python3 -m unittest discover -s tests -v` from this directory. Tests cover migration, threshold boundaries, month lengths and leap years, repeat payments, early payments, concurrent calls, restart persistence, disabled auto advance, history retention, invalid edits, and double-rollover prevention. Manager tests use in-memory Home Assistant storage/time doubles; they are not a live Home Assistant runtime test. Python compilation and JSON/YAML structure checks also pass.
