# AGENTS.md

## Scope

This folder owns user workflows, layout, forms, dashboards, tables, navigation, and API consumption.

The frontend must stay clean, user-friendly, fast, and highly functional for real business operations.

---

## UI/UX Principles

### Business-first design
The UI is an operational tool, not a decorative website. Every screen must help users complete business tasks quickly and correctly.

### Clarity over visual noise
Prefer simple, clear layouts over trendy or flashy design. Avoid clutter, oversized components, and unnecessary visual effects.

### High functionality
Support real business workflows with:
- strong table views
- filtering
- searching
- sorting
- pagination where needed
- variant-aware selection
- status visibility
- efficient forms

### Low-friction workflows
Reduce clicks and cognitive load for common tasks such as:
- receiving stock
- finding a product variant
- recording a sale
- processing returns
- checking inventory
- viewing reports

### Consistency
Use shared patterns for:
- buttons
- inputs
- modals
- tables
- page headers
- actions
- validation messages

Do not invent one-off UI patterns unless there is a strong reason.

### Role-aware UI
Owners, managers, warehouse users, and staff do not need the same screen complexity.
Show users what they need for their role. Hide what they do not need.

### Accurate business semantics
Do not hide or blur the distinction between product and variant where it matters.
If the backend requires `variant_id`, the UI must make variant selection explicit and understandable.

### Density with readability
This is business software. Information density is acceptable, but it must remain readable and organized.
Avoid excessive whitespace that reduces efficiency.

### Responsive but practical
The UI should work on smaller screens, but desktop productivity for business operators is a primary concern.

---

## Frontend Rules

- Do not invent client-side business logic that conflicts with backend truth.
- Do not hide backend/data-model problems with UI hacks.
- Keep forms aligned with API payload requirements.
- Keep validation messages clear and actionable.
- Keep navigation predictable.
- Prefer reusable components over repeated custom UI.
- Keep state management simple and maintainable.
- Avoid unnecessary re-renders, polling, and wasteful API calls.

---

## Tables and Forms

### Tables
Operational screens should prefer tables when users need:
- scanning
- comparison
- filtering
- bulk review
- quick action

### Forms
Forms must:
- capture all required business fields
- avoid irrelevant fields
- group related inputs logically
- clearly show required vs optional data
- make variant selection easy when stock depends on variant identity

---

## Dashboard Rules

Dashboards must be useful, not decorative.

Show:
- actionable KPIs
- trends
- alerts
- stock issues
- slow-moving items
- sales performance

Do not overload dashboards with non-actionable visual clutter.

---

## Performance and Cost

Frontend must be efficient because unnecessary requests increase backend load and AWS cost.

Avoid:
- excessive polling
- duplicate fetching
- large overfetched payloads
- rendering heavy components without need
