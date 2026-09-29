# Monthly Bills for Home Assistant

An experimental local custom integration. **Back up your Home Assistant configuration, including `.storage/monthly_bills.data`, before updating.** This version reuses the existing storage key and original sensor unique IDs, so existing bill records and status sensor registry entries should persist.

## Install / update

1. Unzip and copy `custom_components/monthly_bills/` into `/config/custom_components/monthly_bills/` (replace the old folder; don't nest it).
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Integrations → Monthly Bills**. The manifest is now of type `hub` rather than `helper`.
4. To create or delete bills, select **Configure** on the integration, then **Add a bill** or **Delete a bill**. Reopen Configure to add another.
5. Under the integration's **Devices**, each bill is a device exposing:
   - `sensor.bill_<id>` status and attributes (existing sensor unique IDs preserved)
   - `number.bill_<id>_amount`: editable cost
   - `date.bill_<id>_due_date`: editable date
   - `switch.bill_<id>_paid`: editable Paid switch
   - `text.bill_<id>_category`: editable category

The entity IDs shown are typical; Home Assistant may assign a different ID if an existing ID is in use. Device Info shows the controls but the actual edits are performed through the entity's More Info controls, not by editing arbitrary attributes. The status sensor reflects changes immediately.

## Existing actions

The original `monthly_bills.add_bill`, `update_bill`, `mark_paid`, `mark_unpaid`, `rollover`, and `delete_bill` actions remain available. Monthly rollover preserves unpaid overdue bills and archives paid bills when advanced. The integration's data remains in `.storage/monthly_bills.data`.

## Caveats

This is a locally generated prototype, not an official Home Assistant integration and not tested in a live Home Assistant runtime. First test with one bill and check Settings → System → Logs after upgrading. No live payment processing is performed.

## Version 0.2.1 fix
Corrects Add bill input normalization (date and numeric values), ensures missing optional category is handled, preserves entered values when a save fails, and writes the real exception to the HA logs as `Unable to add Monthly Bills record`. Replaces the generic misleading validation message. Does not change the storage schema.
