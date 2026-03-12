# AGENTS.md

## Scope

This folder owns user workflows, forms, dashboards, and API consumption.

---

## Rules

- Frontend must reflect real backend business rules.
- Do not invent client-side business logic that conflicts with backend truth.
- Do not hide data quality problems with cosmetic UI workarounds.
- Product selection and variant selection must be explicit where saleable stock depends on variant attributes.
- Role-based visibility must be enforced in UI, but backend remains the source of authorization truth.

---

## Form Discipline

- Do not submit ambiguous product-only payloads when variant identity is required.
- Inventory, purchase, and sales workflows must collect the identifiers required for correct backend writes.
- Ensure user-facing labels make product vs variant distinction clear.

---

## Dashboard Discipline

- Dashboard metrics must come from approved backend sources.
- Do not compute financial or stock truth in the browser when authoritative backend values exist.
