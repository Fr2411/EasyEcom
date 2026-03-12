# AGENTS.md

## Scope

This folder owns API behavior, validation, service logic, transaction orchestration, authorization enforcement, and persistence behavior.

---

## Rules

- Backend is the enforcement layer for business truth.
- Do not trust frontend payload semantics without validation.
- Every mutating flow must be tenant-safe and role-aware.
- Inventory-affecting operations must write auditable transaction records.
- Variant-level stock rules must be enforced here.
- Use database transactions where consistency matters across multiple writes.
- Avoid hidden side effects.
- Keep services small, explicit, and testable.

---

## Inventory Rules

- New inventory-affecting writes must reference `variant_id`.
- Reads of available stock must resolve from ledger truth or approved derived totals.
- Do not deduct stock from parent product abstractions.
- Returns and adjustments must use explicit typed flows.

---

## API Contract Discipline

- Keep request/response shapes stable unless a breaking change is intentional and documented.
- If the frontend must change with the backend, update both in the same task.
- Never silently repurpose an existing field to mean something different.

---

## Performance / Cost

- Avoid N+1 queries.
- Avoid full-table scans on tenant traffic paths.
- Use indexes intentionally.
- Prefer exact targeted queries over broad overfetching.
