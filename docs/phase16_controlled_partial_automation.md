# Phase 16 — Controlled Partial Automation

## What was implemented

Phase 16 adds a tenant-scoped controlled partial automation layer on top of Phase 14 channel conversations and Phase 15 human-reviewed drafts.

Implemented capabilities:
- Explicit tenant automation policy model (enable/disable, auto-send gate, emergency stop, per-category toggles).
- Deterministic low-risk classifier for inbound messages.
- Evaluate + run endpoints that either auto-send grounded low-risk responses or escalate to human review.
- Reuse of Phase 15 `ai_review_drafts` as the human fallback artifact.
- Dedicated `automation_decisions` audit trail for every automation run.
- Internal automation operations UI in Next.js.

## Endpoints/services added or changed

### New backend routes (`/automation`)
- `GET /automation/policies`
- `PATCH /automation/policies`
- `POST /automation/enable`
- `POST /automation/disable`
- `POST /automation/evaluate/{conversation_id}`
- `POST /automation/run/{conversation_id}`
- `GET /automation/history`
- `GET /automation/queue`

All routes require:
- authenticated session
- `Automation` page access
- admin/owner/manager role
- strict `client_id` scoping from the authenticated user

### New service
- `AutomationService` in `easy_ecom/domain/services/automation_service.py`
  - policy storage and mutation
  - low-risk message classification
  - evaluation decisioning
  - controlled auto-send path via existing `IntegrationsService.prepare_outbound`
  - fallback draft creation in existing `ai_review_drafts`
  - audit history/queue retrieval

## Policy and decision model

### Policy entity
`tenant_automation_policies`
- `automation_enabled`
- `auto_send_enabled`
- `emergency_disabled`
- `categories_json`

Supported low-risk categories in MVP:
- `product_availability`
- `stock_availability`
- `simple_price_inquiry`
- `business_hours_basic_info`

### Decision/audit entity
`automation_decisions`
- classification metadata (`category`, `classification_rule`)
- policy link (`policy_id`)
- decision and execution state (`recommended_action`, `outcome`, `reason`)
- candidate reply + confidence snapshot
- structured audit context (`audit_context_json`)
- actor and timestamps

## Tenant isolation and safety rules

- Every query/write is scoped by `client_id` from authenticated user context.
- Automation is disabled by default.
- Auto-send executes only when all are true:
  - policy enabled
  - emergency disabled is false
  - category is explicitly enabled
  - classification is low-risk and explicit
  - generated response confidence is `grounded`
- Unsupported or ambiguous messages are escalated.
- Failed auto-send attempts create fallback review drafts and persist failure reason in audit history.

## Auto-send vs human-review rules

- `evaluate` returns eligibility + recommended action only.
- `run` persists a decision row and then:
  - `auto_sent` when policy allows and dispatch succeeds
  - `drafted` when human review is required
  - `escalated` for blocked/unsupported/ambiguous messages
  - `failed` when dispatch fails (with fallback review draft)

## Audit behavior

- Every run writes `automation_decisions` with reason and context.
- History endpoint returns all decisions.
- Queue endpoint filters to non-auto-sent outcomes (`drafted`, `escalated`, `failed`) for operator follow-up.

## Deferred for future phases

- No open-ended autonomous agent behavior.
- No autonomous operational writes from chat.
- No long-horizon memory/feedback loops.
- No mass outbound campaigns.
- No provider-specific delivery adapters beyond existing deferred outbound intent model.

## How this prepares future automation

Phase 16 establishes a safe governance and observability layer that can be expanded with richer classifiers, confidence gates, and provider adapters without sacrificing tenant isolation or human override controls.
