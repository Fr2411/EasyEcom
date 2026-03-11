# Phase 15 — Human-Reviewed AI Response Workflow

## What was implemented

Phase 15 adds a tenant-safe AI review workflow on top of the existing Phase 13 AI context layer and Phase 14 channel conversation foundation.

Delivered capabilities:
- AI review queue for inbound channel conversations
- Grounded AI candidate reply generation from tenant-scoped context
- Human edit / approve / reject controls
- Explicit approval gate before send
- Outbound send path routed through existing Phase 14 `prepare_outbound` dispatch preparation
- Auditable persistence of AI draft, human changes, approval, send outcome, and actor/timestamps

## Backend endpoints added

All endpoints are authenticated, role-restricted (owner/manager/admin), and tenant-scoped by `user.client_id`:

- `GET /ai/review/conversations`
- `GET /ai/review/conversations/{conversation_id}`
- `POST /ai/review/draft`
- `POST /ai/review/{draft_id}/edit`
- `POST /ai/review/{draft_id}/approve`
- `POST /ai/review/{draft_id}/reject`
- `POST /ai/review/{draft_id}/send`
- `GET /ai/review/history`

## Services and state model

Primary service: `AiReviewService`.

Generation flow:
1. Validate tenant and inbound message ownership
2. Call Phase 13 `AiContextService.handle_inbound_inquiry`
3. Produce deterministic, grounded candidate text via `AiDraftGenerator`
4. Persist draft as `draft_created`

State transitions:
- `draft_created`
- `edited`
- `approved`
- `rejected`
- `sent`
- `failed`

Send flow rules:
- send is rejected unless state is `approved`
- sending uses Phase 14 outbound preparation service (`IntegrationsService.prepare_outbound`)
- send result is persisted in `send_result_json`
- failures set state to `failed` with `failed_reason`

## Schema/entities/config used

New table: `ai_review_drafts`.

Stored fields include:
- inbound reference: `conversation_id`, `inbound_message_id`
- AI output: `ai_draft_text`, `intent`, `confidence`, `grounding_json`
- human output: `edited_text`, `final_text`
- audit actors: `requested_by_user_id`, `approved_by_user_id`, `sent_by_user_id`
- timeline: `created_at`, `updated_at`, `approved_at`, `sent_at`
- send outcome: `status`, `failed_reason`, `send_result_json`

Migration: `easy_ecom/migrations/20260317_phase15_ai_review_workflow.sql`.

## Tenant isolation and approval rules

- Every query for drafts/conversations/messages is scoped by `client_id`
- Draft operations fail when the draft/message/conversation does not belong to the caller tenant
- Role checks re-use existing owner/manager/admin permission model
- No auto-send behavior exists in this phase
- Human approval is mandatory before send

## Audit behavior

Auditability includes:
- source inbound message ID
- generated draft text
- edited/final text
- status progression
- approving/sending user IDs
- send attempt result payload

This gives a traceable line from inbound event -> AI suggestion -> human approval -> outbound preparation intent.

## Intentionally deferred

- Autonomous sending/auto-approval
- Multi-turn autonomous memory orchestration
- Provider-specific live delivery adapters
- Prompt experimentation interface
- Fine-tuning/training toolchain

## Phase 16 readiness

Phase 15 prepares safe progression to controlled automation by:
- enforcing explicit state machine transitions
- preserving actor and content audit data
- keeping generation provider abstraction replaceable (`AiDraftGenerator`)
- reusing existing channel and AI context service contracts without bypassing tenant safety
