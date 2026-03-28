# Automation Module Implementation Brief

## Objective
Automation should become a tenant-safe rule engine for EasyEcom, not a general-purpose workflow sandbox. The first release must solve operational follow-up work for commerce tenants while staying cheap, auditable, and easy to reason about.

## Current State
- The `/automation` frontend route is still a placeholder.
- There is no dedicated backend automation router in the current runtime.
- Related capabilities already exist in adjacent modules:
  - `sales_agent` handles conversations, drafts, and outbound messaging.
  - `ai_review` handles human approval of outbound drafts.
  - `integrations` handles WhatsApp channel configuration and diagnostics.
  - `settings` stores tenant defaults, prefixes, and channel preferences.

## Scope
Automation v1 should cover a narrow set of business-safe tasks:
- Low-stock alerts based on variant-level ledger truth.
- Stale draft order follow-ups.
- Human-review reminder tasks for AI drafts.
- Channel failure alerts and retry reminders.
- Daily or weekly operational digests.
- Explicitly approved outbound messages, only when the action is already safe and tenant-scoped.

Automation v1 must not:
- Mutate inventory directly.
- Create unapproved outbound customer messages.
- Run arbitrary code or user-defined scripts.
- Replace the ledger or transaction services.
- Bypass `sales_agent` or `ai_review` approval rules.

## Data Model
Use a small, auditable schema with tenant-scoped foreign keys.

| Table | Purpose | Core Fields |
| --- | --- | --- |
| `automation_rules` | Main rule definition | `automation_rule_id`, `client_id`, `name`, `status`, `trigger_type`, `trigger_key`, `schedule_rule`, `timezone`, `condition_json`, `enabled_by_user_id`, `last_run_at`, `next_run_at` |
| `automation_rule_actions` | Ordered actions for a rule | `automation_rule_action_id`, `automation_rule_id`, `action_type`, `action_order`, `action_config_json`, `requires_approval`, `is_active` |
| `automation_runs` | Execution history | `automation_run_id`, `automation_rule_id`, `client_id`, `status`, `trigger_source`, `started_at`, `finished_at`, `error_code`, `error_message`, `input_snapshot_json`, `result_snapshot_json`, `request_id` |
| `automation_run_events` | Step-by-step trace for a run | `automation_run_event_id`, `automation_run_id`, `event_type`, `event_status`, `message`, `metadata_json`, `created_at` |

Implementation notes:
- Keep rule conditions as structured JSON, not free-form code.
- Model all trigger inputs against existing business IDs such as `variant_id`, `product_id`, `customer_id`, `sales_order_id`, `channel_id`, and `draft_id`.
- If the first release only needs one action per rule, still keep the actions table so the design can expand without schema churn.
- Store `client_id` on every row that can be queried directly.

## API Surface
The backend should expose a dedicated router with a small contract.

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/automation/overview` | Tenant/module summary and counts |
| `GET` | `/automation/rules` | List rules with status, trigger, next run, and last run |
| `POST` | `/automation/rules` | Create a rule |
| `GET` | `/automation/rules/{rule_id}` | Rule detail |
| `PATCH` | `/automation/rules/{rule_id}` | Update editable fields |
| `POST` | `/automation/rules/{rule_id}/enable` | Enable a rule |
| `POST` | `/automation/rules/{rule_id}/disable` | Disable a rule |
| `POST` | `/automation/rules/{rule_id}/run` | Manual tenant-scoped run for testing and operational recovery |
| `GET` | `/automation/rules/{rule_id}/runs` | Run history for one rule |
| `GET` | `/automation/runs` | Cross-rule run history for the tenant |
| `GET` | `/automation/templates` | Starter templates for common commerce workflows |

API rules:
- Every write path must require tenant authorization.
- Super admin access should only be used for cross-tenant diagnostics or support.
- Rule creation and edits must be audited.
- Manual run requests must capture the initiating user and request ID.

## UI Surface
The frontend should replace the placeholder route with a real workspace built around three panels.

### Landing View
- Show active rules, disabled rules, and recent failures.
- Surface next scheduled runs and the last successful run.
- Show a clear empty state when the tenant has not configured anything yet.

### Rule Builder
- Configure name, status, trigger type, and target scope.
- Support only simple trigger choices in v1:
  - scheduled hourly or weekly run
  - variant stock threshold
  - stale draft order age
  - AI draft waiting age
  - channel diagnostic failure
- Configure actions from a limited catalog.

### History and Trace
- Show run rows with timestamp, status, trigger source, and error summary.
- Drill into a run to inspect its input snapshot and action results.
- Keep errors readable for operators, not only for engineers.

## Rollout Phases
### Phase 1
- Create schema and migrations.
- Add backend router and service skeleton.
- Support read-only listing and run history.
- Add tenant-safe overview metrics.

### Phase 2
- Implement rule creation, update, enable, disable, and manual run.
- Add one or two safe actions, such as internal notification and review task creation.
- Add frontend workspace and template picker.

### Phase 3
- Add scheduled execution.
- Add stock-threshold and stale-workflow templates.
- Add automatic run processing and failure handling.

### Phase 4
- Add operational polish: retry policy, alerting hooks, and richer diagnostics.
- Expand templates only after the first workflows are stable in production.

## Audit And Safety Rules
- All automation rules must be tenant-scoped.
- No rule may bypass ledger truth for stock-related decisions.
- No rule may send external messages without explicit approval when approval is required by the downstream flow.
- No rule may silently mutate inventory, sales, returns, or customer records.
- Every automated action must create an auditable run record.
- Every manual execution must preserve the acting user and request ID.
- Any action that touches customer communication must reuse `sales_agent` and `ai_review` safeguards.
- Keep the first version intentionally small. A smaller, reliable rule engine is better than a broad but brittle workflow system.

## Success Criteria
- A tenant can create a rule, see when it will run, run it manually, and inspect execution history.
- The UI no longer shows the automation placeholder.
- The system can safely surface operational alerts without risking tenant data isolation or inventory correctness.
- The module can scale later without requiring schema redesign.
