# Phase 13 — AI Readiness Foundation

## What was implemented

Phase 13 introduces a backend-first AI-ready data access layer on the canonical FastAPI + PostgreSQL architecture. The implementation adds tenant-scoped, read-only AI context endpoints and automation hooks that shape existing business truth into compact, typed contracts.

This phase intentionally does **not** deploy WhatsApp/Messenger/public bot integrations and does **not** allow free-form SQL or direct LLM-to-database access.

## API endpoints added

All endpoints are authenticated, tenant-scoped via session `client_id`, and guarded by existing page access checks.

### AI context
- `GET /ai/context/overview`
- `GET /ai/context/products`
- `GET /ai/context/stock`
- `GET /ai/context/low-stock`
- `GET /ai/context/sales`
- `GET /ai/context/customers`
- `GET /ai/context/lookup`
- `GET /ai/context/recent-activity`

### Automation hook (internal-safe contract)
- `POST /ai/hooks/inbound-inquiry`

## Service layer added

`AiContextService` (PostgreSQL-backed) provides reusable methods:
- overview snapshot (products, variants, customers, sales, low-stock count)
- product + variant + pricing summary
- stock availability summary
- low stock summary
- recent sales and top-product summary
- customer lookup summary
- sale/product/customer lookup contract
- recent activity summary from sales and inventory ledgers
- inbound inquiry classification hook contract for future channel adapters

## Tenant isolation and AI safety rules in implementation

- Session-authenticated user is required.
- Every read query is constrained by `client_id`.
- No endpoint accepts tenant override parameters.
- No write actions in AI context endpoints.
- No direct SQL execution pathway exposed.
- Output contracts are compact and typed, avoiding raw table dumps.
- Inbound inquiry hook returns safe guidance + context and includes explicit guardrail flags.

## Schema / migration / config changes

- No database schema migration was required for this phase.
- Existing `tenant_settings.low_stock_threshold` is reused where present.
- Phase remains backend service/API contract focused.

## Testing added

Added API tests covering:
- unauthenticated rejection
- tenant-scoped behavior
- lookup validation boundaries
- low-stock + empty dataset behavior
- automation hook contract behavior

File: `easy_ecom/tests/test_api_ai_context.py`

## Deferred intentionally

- External channel connectors (WhatsApp/Messenger)
- Public chatbot UX
- LLM provider orchestration
- Autonomous action-taking agents
- Natural-language-to-SQL execution
- AI write operations

## How this prepares Phase 14

Phase 13 creates the production-safe context layer and hook contracts that future integrations can call without bypassing business truth or tenancy boundaries.

Recommended next step for Phase 14:
- implement channel adapter layer (e.g., webhook handlers) that maps inbound channel payloads to these AI-safe contracts, with explicit signed system identity and auditable request logs.
