# AI Communication Hardening Plan

> For Hermes: implement directly on `develop` using test-first changes where practical.

Goal: improve EasyEcom AI conversation quality and trust for tenant-owned website chat without rebuilding the whole stack in one pass.

Architecture: keep the current tenant-safe commerce boundary, but harden the public chat flow and redesign reply generation around cleaner conversation context, safer parsing, and stronger handoff behavior. Add a small backend test foundation so future AI changes stop being guesswork.

Tech stack: FastAPI, SQLAlchemy, Python unittest, Next.js, TypeScript.

---

## Task 1: Add backend AI conversation regression tests
Objective: create a minimal automated safety net for the most important AI behaviors.

Files:
- Create: `tests/test_ai_chat_service.py`
- Create: `tests/test_ai_router.py`

Tests to cover:
- prompt builder replays real conversation turns instead of only one JSON blob
- model parser extracts JSON safely and fails closed when it cannot
- handoff conversations do not continue auto-replying unless reopened
- public chat surfaces use configured assistant display name / opening message when rendered

Verification:
- Run: `python3 -m unittest discover -s tests -v`

## Task 2: Redesign model message construction
Objective: make the AI receive cleaner, more human-like conversation context.

Files:
- Modify: `easy_ecom/domain/services/ai_chat_service.py`

Changes:
- build messages as:
  - system behavior contract
  - system business/policy/catalog context in readable text
  - alternating prior user/assistant turns from stored recent messages
  - current user turn as the latest message
- keep structured action contract for order confirmation / handoff
- improve style instructions for warmth, brevity, and one-question-at-a-time behavior
- remove fallback behavior that feeds arbitrary catalog items when no real match exists

Verification:
- Run AI unit tests
- Run: `python3 -m compileall easy_ecom`

## Task 3: Harden model response parsing and handoff flow
Objective: make AI behavior safer and more predictable.

Files:
- Modify: `easy_ecom/domain/services/ai_chat_service.py`

Changes:
- robustly extract JSON payloads from model output when possible
- if parsing still fails, return safe handoff payload instead of raw free text
- once a conversation is already in `handoff`, do not let AI keep auto-replying until status is reopened through the existing control path

Verification:
- Run AI unit tests
- Run: `python3 -m compileall easy_ecom`

## Task 4: Fix tenant-facing greeting and assistant branding
Objective: make the public website chat feel like the tenant’s assistant, not a generic demo bot.

Files:
- Modify: `easy_ecom/api/routers/ai.py`
- Modify: `easy_ecom/domain/services/ai_chat_service.py`

Changes:
- inject configured display name and opening message into the standalone public chat page
- update the embed widget bootstrap so the first AI greeting uses tenant-configured copy rather than hardcoded generic text
- keep existing widget/public link behavior compatible

Verification:
- Run router/unit tests
- Run frontend typecheck/build after API string changes

## Task 5: Improve the staff AI workspace for trust
Objective: give tenants more visibility into what the AI actually said.

Files:
- Modify: `easy_ecom/domain/services/ai_chat_service.py`
- Modify: `easy_ecom/api/schemas/ai.py`
- Modify: `easy_ecom/api/routers/ai.py`
- Modify: `frontend/lib/api/ai.ts`
- Modify: `frontend/types/ai.ts`
- Modify: `frontend/components/ai/ai-assistant-workspace.tsx`

Changes:
- add authenticated conversation detail endpoint returning recent transcript for one conversation
- let workspace users open a conversation and inspect recent inbound/outbound turns
- surface handoff state clearly

Verification:
- Run backend tests
- Run frontend typecheck/build

## Task 6: Full verification and review
Objective: make sure the changes are stable before leaving them on develop.

Verification commands:
- `python3 -m unittest discover -s tests -v`
- `python3 -m compileall easy_ecom`
- `npm run typecheck` (from `frontend/`)
- `npm run build` (from `frontend/`)
- review git diff and summarize remaining gaps for a later phase (operator inbox, stronger auth, idempotency, abuse protection, analytics)
