# Business Rules (Source of Business Truth)

## 1) Product and Variant Rules
- `product` is catalog-level identity used for naming, categorization, and parent grouping.
- `variant` is the saleable stock-level identity (size/color/configuration).
- Any operation that changes, reserves, sells, returns, or reports stock must use `variant_id`.
- Product-level availability is derived by aggregating eligible variants, never by storing stock at product level.

## 2) Stock Movement Rules
- Inventory is ledger-driven; each movement is an immutable transaction event.
- Movement types include purchase-in, sale-out, return-in, return-out, adjustment, transfer (if enabled), and opening balance.
- No stock mutation is allowed without a ledger record.
- Derived stock snapshots/caches are optional optimizations and must reconcile to ledger totals.

## 3) Sale and Return Rules
- Sales lines must map to `variant_id` and capture unit price, quantity, and discount context.
- A sale reduces available stock at variant level.
- Returns must reference original sale lines where possible and restore/reverse stock via explicit return transactions.
- Financial reversals from returns must be explicit and auditable.

## 4) User Role Rules
- Tenant users are role-bound (owner/admin/staff/warehouse as configured).
- Backend authorization is authoritative; frontend visibility is supportive.
- Super admin can perform cross-tenant operations; tenant roles cannot.

## 5) Pricing Rules
- Products/variants may have default selling prices and discount constraints.
- Any promotional or AI-assisted pricing must honor tenant-defined bounds.
- Final billed line values must remain auditable and reproducible from stored transaction data.

## 6) Tenant Rules
- All reads/writes must be tenant-scoped unless explicitly super-admin.
- Every transactional row must carry tenant-safe foreign keys.
- Cross-tenant joins/caches/reports are forbidden in tenant-facing paths.

## 7) AI Usage Rules
- AI must only access data authorized for the acting tenant.
- Availability responses must resolve from variant-level stock truth.
- AI must not promise unavailable stock, invalid pricing, or unauthorized catalog data.
- Human-review controls remain mandatory for risky outbound communication flows.
- Customer communication AI must receive backend-prepared facts for price, stock, customer, recommendation, policy, memory, and draft-order data; raw SQL access is forbidden.
- Customer-facing AI sales wording should be model-composed from tenant-safe context, not assembled from canned backend response templates.
- Tenant playbooks may shape tone and domain questions, but they cannot override tenant isolation, variant-level stock, pricing bounds, or escalation requirements.
