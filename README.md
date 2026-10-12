# Monthly Bills for Home Assistant — v0.3.7

A local, editable monthly bill tracker. This release upgrades the v0.2.3 source and retains the storage key, bill IDs, device identifiers, and all existing entity unique IDs.

## v0.3.7 — Autopay toggle for every bill

Each bill now has an **Autopay** switch, normally `switch.rent_autopay`. It records whether you have enabled automatic payment with the bill provider. This is independent of the Paid and Auto advance switches: toggling Autopay does not record a payment, advance a due date, or initiate a payment. Existing payment/status behavior continues unchanged.

The first upgrade initializes Autopay On for existing bills categorized as **Automatic** (case-insensitive, trimmed), and Off otherwise. Explicitly saved Autopay values are preserved on later restarts. The category itself remains unchanged. After migration, Autopay and category are separate fields; changing one does not overwrite the other.

New bills default to Autopay Off. The native Add Bill form and dashboard badge dialog include the toggle. Badge configuration supports `default_autopay: true` if you want new bills to default On.

The status sensor exposes an `autopay` boolean, and calendar event descriptions show Autopay Yes/No. You can set it through its native switch or the existing actions:

```yaml
action: monthly_bills.update_bill
data:
  bill_id: rent
  autopay: true
```

Upload the package contents, commit and publish **0.3.7**, update through HACS, restart Home Assistant and refresh the browser. If you added a manual badge resource after v0.3.6, update its URL to `/monthly_bills_static/monthly-bills-badge.js?v=0.3.7` so the new form fields load.

The saved bill-card template provided separately reads `switch.<bill_id>_autopay` for its AUTOPAY label. Its category-based fallback keeps the label working before the integration upgrade. Existing icon/lock/PIN styling remains as supplied by the user.

Validation includes migration, explicit false preservation, toggle persistence, category independence, unchanged payment fields, and no automatic payment recording. Frontend tests verify the new checkbox default, configurable default and service payload. All 44 Python tests and 12 frontend DOM tests pass. Live Home Assistant verification is still needed.

## v0.3.6 — Add Bill dashboard badge

A bundled frontend component adds a badge that opens a form for creating a bill. It uses the existing `monthly_bills.add_bill` action and requires no Browser Mod, helper entities or additional HACS frontend download. The integration automatically serves and loads the versioned JavaScript module at startup using Home Assistant's frontend API. Do not also add it as a dashboard resource.

Upgrade through the same repository/release workflow using version **0.3.6**, then update in HACS, restart Home Assistant, and refresh your browser. Keep the existing integration configured.

Add this to the desired view's `badges:` list (not to `button_card_templates:`):

```yaml
badges:
  - type: custom:monthly-bills-add-badge
    name: Add bill
    icon: mdi:plus
```

The same badge is registered in the badge picker as **Monthly Bills: Add bill**. The standalone badge config is also provided in `examples/add_bill_badge.yaml`. No entity ID is needed.

The form collects bill name, amount in USD, next due date, category, auto-advance and upcoming threshold. Auto-advance defaults On and threshold defaults to 7 days. Dates default to today in Home Assistant's configured time zone. You can override form defaults in the badge YAML:

```yaml
type: custom:monthly-bills-add-badge
name: Add bill
icon: mdi:plus
default_category: Utilities
default_auto_advance: true
default_upcoming_threshold: 7
```

Click **Add bill** to save. While saving, duplicate submissions and dialog cancellation are blocked. On success the form closes and a confirmation is announced. Existing integration updates create the new bill entities and refresh the calendar. Failed saves display the error and keep your entered values. A new bill is unpaid; entering a due date does not record a payment. The badge is disabled until the integration's Add Bill action is available.

If the badge type is not found after restart, hard-refresh the browser (Ctrl+F5). Check Home Assistant logs for Monthly Bills startup errors if it remains unavailable. The bundle uses a guard against duplicate custom-element registration.

Validation: 40 Python tests and 12 JavaScript DOM tests passed, including service payloads, failed saves/retry, double-click protection, input validation, dialog defaults, state updates, registration and cleanup. JavaScript DOM tests use jsdom with a native-dialog test double; this is not live Home Assistant testing. Run the Python suite with `python3 -m unittest discover -s tests -v`. For frontend tests, install jsdom as a development dependency (`npm install --no-save jsdom`) and run `node --test tests/test_badge.cjs`. Python/JavaScript syntax, JSON/YAML and manifest checks passed. Live Home Assistant/browser verification is still needed.

## v0.3.5 — Due dates calendar

The integration now creates one read-only **Monthly Bills** calendar, normally `calendar.monthly_bills`. It appears in Home Assistant's Calendar sidebar and can be selected in a native calendar dashboard card.

Each bill's currently stored due date becomes a one-day all-day event. The title includes its name and amount, for example **Rent — $1,400.00**. Event details include the amount, due date, status for that due occurrence, category, last payment date and bill ID. Multiple bills on the same day remain separate events.

Adding/deleting a bill, editing a due date, changing an amount/name/category, correcting a payment date, or recording a payment refreshes calendar subscribers. When auto advance moves the due date, the calendar event moves with it. A previous-cycle Paid acknowledgement does not mark the next calendar occurrence as paid. With auto advance disabled, a paid bill stays on its stored due date with Paid in its description.

This calendar displays actual stored due dates, not forecasts of every future monthly cycle or a payment-history calendar. Overdue bills remain visible on their original due dates when viewing that date range. Edit bills through their existing controls rather than directly in the calendar.

Dashboard card (also included in `examples/bills_calendar_card.yaml`):

```yaml
type: calendar
title: Bills Due
initial_view: dayGridMonth
entities:
  - calendar.monthly_bills
```

For an agenda, use `initial_view: listWeek`. If Home Assistant assigns a different entity ID, select the Monthly Bills calendar's actual ID in the card editor.

Upgrade by committing the package contents to the repository and publishing **0.3.5**. Update through HACS and restart Home Assistant. The calendar platform is set up automatically for the existing integration; do not remove/re-add Monthly Bills. Existing bills, payment history and entity IDs are preserved.

Validation: 39 automated tests passed using in-memory Home Assistant doubles, including calendar date-range boundaries, DST, UTC-to-local conversion, multiple simultaneous due dates, event movement after payment, non-next-event changes, and listener cleanup. Python syntax and JSON/YAML checks also passed. The Calendar API was checked against Home Assistant 2026.9.2 source; live Home Assistant testing is still needed.

## v0.3.4 — Fix latest-payment date correction

Removes an overly strict comparison between the last archived payment's due date and the stored last-paid-cycle marker. Correcting the latest history record now works even when those two fields disagree. The editor leaves the billing-cycle marker, next due date, paid status, amount and earlier history entries unchanged. It continues to reject corrections when no payment record exists and rejects invalid or future dates. Current unarchived paid occurrences still take precedence over older archived payments.

Publish release **0.3.4**, update through HACS, and restart Home Assistant. Then retry the existing Last payment date editor. No data-file editing is needed for this correction. All 28 automated tests pass, including mismatched markers both before and after the Upcoming transition. Live Home Assistant verification is still needed.

## v0.3.3 — Correct the latest payment date

Automatic payment recording, monthly date advancement, and the upcoming threshold continue as before. Each bill now exposes a date entity named **Last payment date**, normally `date.rent_last_payment_date` for Rent. Open this entity's More Info dialog to correct the latest payment date. The existing `sensor.rent_last_paid` and status sensor's `last_paid_on` attribute reflect the correction, so existing cards need no changes.

The editor changes the last archived payment's `paid_on` date, or the current unarchived payment when auto advance is disabled. It keeps the related payment date fields consistent. Older history entries, amount, billing-cycle due date, next due date, and paid status remain unchanged. It does not record a new payment or advance a month. A bill with no recorded payment cannot be backfilled through this correction control; first record the real payment. Invalid and future dates are rejected.

To correct through Developer Tools → Actions:

```yaml
action: monthly_bills.update_last_payment_date
data:
  bill_id: rent
  paid_on: "2026-10-01"
```

Example: a test payment recorded on October 12 advanced the bill to November 1. Correcting the payment date to October 1 updates the last payment history record and card's Last paid date, while keeping November 1 as the next due date.

A separate internal recording date preserves same-day retry protection when the displayed payment date is corrected. Existing records are migrated automatically; the storage key/version and all existing entity IDs remain unchanged.

Upload this package's extracted contents to the existing repository root, commit, and publish release **0.3.3** pointing to that commit. Update through HACS and restart Home Assistant. The manifest contains the repository URLs and `codeowners` list for `elecompte/ha-monthly-bills`.

Validation: 26 automated billing/manager tests passed with in-memory Home Assistant doubles, plus Python syntax and JSON/YAML checks. Live Home Assistant validation is still needed.

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
