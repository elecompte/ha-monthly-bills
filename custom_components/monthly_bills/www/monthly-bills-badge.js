/* Monthly Bills Add Bill badge. No external frontend dependencies. */
(() => {
  "use strict";
  const BADGE = "monthly-bills-add-badge";
  const DIALOG = "monthly-bills-add-dialog";

  const localToday = (hass) => {
    const parts = new Intl.DateTimeFormat("en-US", {
      timeZone: hass.config?.time_zone || Intl.DateTimeFormat().resolvedOptions().timeZone,
      year: "numeric", month: "2-digit", day: "2-digit",
    }).formatToParts(new Date());
    const part = (type) => parts.find((item) => item.type === type).value;
    return `${part("year")}-${part("month")}-${part("day")}`;
  };

  class MonthlyBillsAddDialog extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `
        <style>
          :host { font-family: var(--primary-font-family, Roboto, Arial, sans-serif); }
          dialog { box-sizing: border-box; width: min(460px, calc(100vw - 32px));
            max-height: calc(100dvh - 32px); overflow: auto; border: 0;
            border-radius: 20px; padding: 24px; color: var(--primary-text-color, #212121);
            background: var(--card-background-color, #fff);
            box-shadow: 0 16px 60px #0005; }
          dialog::backdrop { background: #0007; }
          h2 { margin: 0 0 6px; font-size: 24px; }
          .intro { margin: 0 0 22px; color: var(--secondary-text-color, #666); font-size: 14px; }
          label { display: block; margin: 0 0 16px; font-size: 14px; font-weight: 500; }
          input:not([type=checkbox]) { display: block; box-sizing: border-box; width: 100%;
            margin-top: 6px; padding: 12px; border: 1px solid var(--divider-color, #ccc);
            border-radius: 10px; font: inherit; color: inherit;
            background: var(--secondary-background-color, #f5f5f5); }
          input:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); }
          .row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
          .check { display: flex; align-items: center; gap: 10px; line-height: 1.4; }
          input[type=checkbox] { width: 20px; height: 20px; accent-color: var(--primary-color, #03a9f4); }
          .hint { margin: -10px 0 18px; font-size: 12px; color: var(--secondary-text-color, #666); }
          .error { color: var(--error-color, #b00020); font-size: 14px; margin: 0 0 14px; white-space: pre-wrap; }
          .error:empty { display: none; }
          .actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 22px; }
          button { border: 0; border-radius: 10px; padding: 11px 18px; font: inherit;
            font-weight: 600; cursor: pointer; background: transparent;
            color: var(--primary-color, #03a9f4); }
          button[type=submit] { background: var(--primary-color, #03a9f4);
            color: var(--text-primary-color, white); }
          button:disabled { opacity: .55; cursor: wait; }
          @media (max-width: 360px) { .row { grid-template-columns: 1fr; gap: 0; } }
        </style>
        <dialog aria-labelledby="heading">
          <h2 id="heading">Add a bill</h2>
          <p class="intro">Track a monthly bill and its next due date.</p>
          <form>
            <fieldset style="border:0;padding:0;margin:0">
              <label>Bill name
                <input name="name" type="text" required maxlength="100" autocomplete="off">
              </label>
              <div class="row">
                <label>Amount (USD)
                  <input name="cost" type="number" required min="0" max="100000000" step="0.01" inputmode="decimal">
                </label>
                <label>Next due date
                  <input name="due_date" type="date" required>
                </label>
              </div>
              <label>Category
                <input name="category" type="text" maxlength="100" autocomplete="off">
              </label>
              <label class="check">
                <input name="autopay" type="checkbox">
                Autopay enabled with the bill provider
              </label>
              <label class="check">
                <input name="auto_advance_due_date" type="checkbox">
                Advance due date when marked paid
              </label>
              <label>Upcoming threshold (days)
                <input name="upcoming_threshold_days" type="number" required min="0" max="30" step="1" inputmode="numeric">
              </label>
              <p class="hint">The default is 7 days before the next due date.</p>
            </fieldset>
            <p class="error" role="alert" aria-live="assertive"></p>
            <div class="actions">
              <button type="button" id="cancel">Cancel</button>
              <button type="submit" id="save">Add bill</button>
            </div>
          </form>
        </dialog>
      `;
      this._dialog = this.shadowRoot.querySelector("dialog");
      this._form = this.shadowRoot.querySelector("form");
      this._field = (name) => this._form.elements.namedItem(name);
      this._error = this.shadowRoot.querySelector(".error");
      this._save = this.shadowRoot.querySelector("#save");
      this._cancel = this.shadowRoot.querySelector("#cancel");
      this._form.addEventListener("submit", (event) => {
        event.preventDefault();
        this._submit();
      });
      this._cancel.addEventListener("click", () => this._dialog.close());
      this._dialog.addEventListener("cancel", (event) => {
        if (this._busy) event.preventDefault();
      });
      this._dialog.addEventListener("close", () => {
        this.onClosed?.();
        this.remove();
      });
    }

    open(hass, config, onSaved, onClosed) {
      this._hass = hass;
      this.onSaved = onSaved;
      this.onClosed = onClosed;
      this._field("due_date").value = localToday(hass);
      this._field("category").value = config.default_category || "Other";
      this._field("auto_advance_due_date").checked = config.default_auto_advance ?? true;
      this._field("autopay").checked = config.default_autopay ?? false;
      this._field("upcoming_threshold_days").value = config.default_upcoming_threshold ?? 7;
      this._dialog.showModal();
      this._field("name").focus();
    }

    _readValues() {
      const name = this._field("name").value.trim();
      const amountText = this._field("cost").value.trim();
      const cost = Number(amountText);
      const due = this._field("due_date").value;
      const thresholdText = this._field("upcoming_threshold_days").value.trim();
      const threshold = Number(thresholdText);
      if (!name || name.length > 100) throw new Error("Enter a bill name (up to 100 characters).");
      if (!amountText || !Number.isFinite(cost) || cost < 0 || cost > 100000000) {
        throw new Error("Enter an amount between $0 and $100,000,000.");
      }
      if (Math.abs(cost * 100 - Math.round(cost * 100)) > 0.000001) {
        throw new Error("Use no more than two decimal places for the amount.");
      }
      const parsedDue = new Date(`${due}T12:00:00Z`);
      if (!/^\d{4}-\d{2}-\d{2}$/.test(due) || !Number.isFinite(parsedDue.getTime()) ||
          parsedDue.toISOString().slice(0, 10) !== due) {
        throw new Error("Choose a valid due date.");
      }
      if (!thresholdText || !Number.isInteger(threshold) || threshold < 0 || threshold > 30) {
        throw new Error("Upcoming threshold must be a whole number from 0 to 30.");
      }
      return {
        name, cost, due_date: due,
        category: this._field("category").value.trim() || "Other",
        auto_advance_due_date: this._field("auto_advance_due_date").checked,
        autopay: this._field("autopay").checked,
        upcoming_threshold_days: threshold,
      };
    }

    _setBusy(busy) {
      this._busy = busy;
      this._form.querySelector("fieldset").disabled = busy;
      this._save.disabled = busy;
      this._cancel.disabled = busy;
      this._save.textContent = busy ? "Adding…" : "Add bill";
      this._form.setAttribute("aria-busy", String(busy));
    }

    async _submit() {
      if (this._busy || this._saved) return;
      this._error.textContent = "";
      let values;
      try {
        values = this._readValues();
      } catch (error) {
        this._error.textContent = error.message;
        return;
      }
      if (!this._form.reportValidity()) return;
      this._setBusy(true);
      try {
        await this._hass.callService("monthly_bills", "add_bill", values);
        this._saved = true;
        this.onSaved?.(values.name);
        this._dialog.close();
      } catch (error) {
        this._error.textContent = error?.message || "Could not add this bill. Check Home Assistant logs.";
        this._setBusy(false);
      }
    }
  }

  class MonthlyBillsAddBadge extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this.shadowRoot.innerHTML = `
        <style>
          :host { display: inline-block; }
          button { display: flex; align-items: center; gap: 8px; min-height: 36px;
            border: 1px solid var(--divider-color, #ddd); border-radius: 20px;
            padding: 6px 12px; background: var(--ha-card-background, var(--card-background-color, white));
            color: var(--primary-text-color, #212121);
            font: 500 14px var(--primary-font-family, Roboto, Arial, sans-serif); cursor: pointer; }
          button:hover { background: var(--secondary-background-color, #eee); }
          button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
          button:disabled { opacity: .5; cursor: default; }
          ha-icon { --mdc-icon-size: 20px; color: var(--primary-color, #03a9f4); }
          .status { position: absolute; width: 1px; height: 1px; overflow: hidden;
            clip-path: inset(50%); }
        </style>
        <button type="button"><ha-icon></ha-icon><span></span></button>
        <span class="status" role="status" aria-live="polite"></span>
      `;
      this._button = this.shadowRoot.querySelector("button");
      this._button.addEventListener("click", () => this._openDialog());
    }

    static getStubConfig() { return { name: "Add bill" }; }

    setConfig(config) {
      if (config.default_upcoming_threshold != null &&
          (!Number.isInteger(config.default_upcoming_threshold) ||
           config.default_upcoming_threshold < 0 || config.default_upcoming_threshold > 30)) {
        throw new Error("default_upcoming_threshold must be a whole number from 0 to 30.");
      }
      if (config.default_auto_advance != null && typeof config.default_auto_advance !== "boolean") {
        throw new Error("default_auto_advance must be true or false.");
      }
      if (config.default_autopay != null && typeof config.default_autopay !== "boolean") {
        throw new Error("default_autopay must be true or false.");
      }
      this._config = { ...config };
      this.shadowRoot.querySelector("button span").textContent = config.name || "Add bill";
      this.shadowRoot.querySelector("ha-icon").setAttribute("icon", config.icon || "mdi:plus");
      this._updateAvailability();
    }

    set hass(hass) {
      this._hass = hass;
      if (this._dialog) this._dialog._hass = hass;
      this._updateAvailability();
    }

    _updateAvailability() {
      this._button.disabled = !this._hass?.services?.monthly_bills?.add_bill;
      this._button.title = this._button.disabled
        ? "Monthly Bills must be configured before adding bills." : "Create a monthly bill";
    }

    _openDialog() {
      if (!this._config || this._button.disabled || this._dialog?.isConnected) return;
      const dialog = document.createElement(DIALOG);
      this._dialog = dialog;
      document.body.appendChild(dialog);
      dialog.open(this._hass, this._config, (name) => {
        this.shadowRoot.querySelector(".status").textContent = `${name} added.`;
        this.dispatchEvent(new CustomEvent("hass-notification", {
          detail: { message: `${name} added.` }, bubbles: true, composed: true,
        }));
        this.dispatchEvent(new CustomEvent("monthly-bills-added", {
          detail: { name }, bubbles: true, composed: true,
        }));
      }, () => {
        this._dialog = null;
        if (this.isConnected) this._button.focus();
      });
    }

    disconnectedCallback() {
      if (this._dialog && !this._dialog._busy) {
        this._dialog._dialog.close();
      }
    }
  }

  if (!customElements.get(DIALOG)) customElements.define(DIALOG, MonthlyBillsAddDialog);
  if (!customElements.get(BADGE)) customElements.define(BADGE, MonthlyBillsAddBadge);
  window.customBadges = window.customBadges || [];
  if (!window.customBadges.some((badge) => badge.type === BADGE)) {
    window.customBadges.push({
      type: BADGE, name: "Monthly Bills: Add bill", preview: false,
      description: "Open a form to create a monthly bill.",
      documentationURL: "https://github.com/elecompte/ha-monthly-bills",
    });
  }
})();
