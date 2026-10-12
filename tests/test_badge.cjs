const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { JSDOM } = require("jsdom");
const source = fs.readFileSync(path.join(__dirname,
  "../custom_components/monthly_bills/www/monthly-bills-badge.js"), "utf8");

function setup(callService = async () => {}) {
  const dom = new JSDOM("<!doctype html><body></body>", {
    runScripts: "outside-only", url: "https://homeassistant.example/",
  });
  const { window } = dom;
  window.HTMLDialogElement.prototype.showModal = function () { this.setAttribute("open", ""); };
  window.HTMLDialogElement.prototype.close = function () {
    this.removeAttribute("open");
    this.dispatchEvent(new window.Event("close"));
  };
  window.eval(source);
  const badge = window.document.createElement("monthly-bills-add-badge");
  badge.setConfig({ type: "custom:monthly-bills-add-badge" });
  badge.hass = {
    config: { time_zone: "America/New_York" },
    services: { monthly_bills: { add_bill: {} } },
    callService,
  };
  window.document.body.appendChild(badge);
  const open = () => {
    badge.shadowRoot.querySelector("button").click();
    return badge._dialog;
  };
  return { dom, window, badge, open };
}

function fill(dialog) {
  dialog._field("name").value = " Rent ";
  dialog._field("cost").value = "1400.25";
  dialog._field("due_date").value = "2026-11-01";
}

test("badge is registered in picker and double loading is safe", () => {
  const env = setup();
  env.window.eval(source);
  assert.equal(env.window.customBadges.length, 1);
  assert.equal(env.badge.shadowRoot.querySelector("button span").textContent, "Add bill");
  env.dom.window.close();
});

test("badge opens one dialog with defaults and input focus", () => {
  const env = setup();
  const dialog = env.open();
  env.open();
  assert.equal(env.window.document.querySelectorAll("monthly-bills-add-dialog").length, 1);
  assert.equal(dialog._field("category").value, "Other");
  assert.equal(dialog._field("auto_advance_due_date").checked, true);
  assert.equal(dialog._field("upcoming_threshold_days").value, "7");
  assert.match(dialog._field("due_date").value, /^\d{4}-\d{2}-\d{2}$/);
  assert.equal(dialog.shadowRoot.activeElement.name, "name");
  env.dom.window.close();
});

test("successful submit sends correct service data and removes dialog", async () => {
  const calls = [];
  const env = setup(async (...args) => calls.push(args));
  const dialog = env.open();
  fill(dialog);
  await dialog._submit();
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [[
    "monthly_bills", "add_bill", {
      name: "Rent", cost: 1400.25, due_date: "2026-11-01", category: "Other",
      auto_advance_due_date: true, upcoming_threshold_days: 7,
    },
  ]]);
  assert.equal(env.badge._dialog, null);
  assert.equal(dialog.isConnected, false);
  assert.equal(env.badge.shadowRoot.querySelector(".status").textContent, "Rent added.");
  await dialog._submit();
  assert.equal(calls.length, 1);
  env.dom.window.close();
});

test("duplicate submit while saving is ignored and Escape is blocked", async () => {
  let resolve;
  let count = 0;
  const env = setup(() => { count++; return new Promise((r) => { resolve = r; }); });
  const dialog = env.open();
  fill(dialog);
  const request = dialog._submit();
  await dialog._submit();
  assert.equal(count, 1);
  assert.equal(dialog._save.disabled, true);
  const cancel = new env.window.Event("cancel", { cancelable: true });
  dialog._dialog.dispatchEvent(cancel);
  assert.equal(cancel.defaultPrevented, true);
  resolve();
  await request;
  env.dom.window.close();
});

test("failed saves retain typed values and allow an explicit retry", async () => {
  let calls = 0;
  const env = setup(async () => {
    calls++;
    if (calls === 1) throw new Error("Storage unavailable");
  });
  const dialog = env.open();
  fill(dialog);
  await dialog._submit();
  assert.equal(dialog.isConnected, true);
  assert.equal(dialog._field("name").value, " Rent ");
  assert.equal(dialog._error.textContent, "Storage unavailable");
  assert.equal(dialog._save.disabled, false);
  await dialog._submit();
  assert.equal(calls, 2);
  assert.equal(dialog.isConnected, false);
  env.dom.window.close();
});

test("invalid name, amount, date and threshold cannot call service", async () => {
  let calls = 0;
  const env = setup(async () => calls++);
  const dialog = env.open();
  for (const [field, value] of [
    ["name", "   "], ["cost", ""], ["cost", "-1"], ["cost", "100000001"],
    ["cost", "1.234"], ["due_date", "2026-02-30"],
    ["upcoming_threshold_days", ""], ["upcoming_threshold_days", "7.5"],
    ["upcoming_threshold_days", "31"],
  ]) {
    fill(dialog);
    dialog._field("upcoming_threshold_days").value = "7";
    dialog._field(field).value = value;
    await dialog._submit();
    assert.equal(calls, 0, field + " " + value);
    assert.notEqual(dialog._error.textContent, "");
  }
  env.dom.window.close();
});

test("zero amount, zero threshold and disabled auto advance are valid", () => {
  const env = setup();
  const dialog = env.open();
  fill(dialog);
  dialog._field("cost").value = "0";
  dialog._field("upcoming_threshold_days").value = "0";
  dialog._field("auto_advance_due_date").checked = false;
  assert.equal(dialog._readValues().cost, 0);
  assert.equal(dialog._readValues().upcoming_threshold_days, 0);
  assert.equal(dialog._readValues().auto_advance_due_date, false);
  env.dom.window.close();
});

test("hass updates do not erase dialog input", () => {
  const env = setup();
  const dialog = env.open();
  fill(dialog);
  env.badge.hass = { ...env.badge._hass };
  assert.equal(dialog._field("name").value, " Rent ");
  assert.equal(dialog._field("cost").value, "1400.25");
  env.dom.window.close();
});

test("cancel closes without service call and restores focus", () => {
  let calls = 0;
  const env = setup(async () => calls++);
  const dialog = env.open();
  dialog._cancel.click();
  assert.equal(calls, 0);
  assert.equal(dialog.isConnected, false);
  assert.equal(env.badge.shadowRoot.activeElement, env.badge._button);
  env.dom.window.close();
});

test("missing service disables badge until integration is available", () => {
  const env = setup();
  env.badge.hass = { services: {}, config: {} };
  assert.equal(env.badge._button.disabled, true);
  env.open();
  assert.equal(env.badge._dialog, undefined);
  env.badge.hass = { services: { monthly_bills: { add_bill: {} } } };
  assert.equal(env.badge._button.disabled, false);
  env.dom.window.close();
});

test("configuration defaults and labels use safe text rendering", () => {
  const env = setup();
  env.badge.setConfig({
    name: "<img src=x onerror=alert(1)>",
    default_category: "Utilities", default_auto_advance: false,
    default_upcoming_threshold: 14,
  });
  assert.equal(env.badge.shadowRoot.querySelector("img"), null);
  const dialog = env.open();
  assert.equal(dialog._field("category").value, "Utilities");
  assert.equal(dialog._field("auto_advance_due_date").checked, false);
  assert.equal(dialog._field("upcoming_threshold_days").value, "14");
  assert.throws(() => env.badge.setConfig({ default_upcoming_threshold: 7.5 }));
  assert.throws(() => env.badge.setConfig({ default_auto_advance: "false" }));
  env.dom.window.close();
});

test("removing badge cleans up an idle dialog", () => {
  const env = setup();
  const dialog = env.open();
  env.badge.remove();
  assert.equal(dialog.isConnected, false);
  env.dom.window.close();
});
