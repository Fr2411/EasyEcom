# AI Shopping Brain Phase 3 Implementation Plan

> For Hermes: follow strict TDD. Add failing tests first, then implement the minimum code to pass, then run the full verification set.

Goal: reduce unnecessary human handoff for normal shopping conversations by adding structured customer preference memory, constraint-aware catalog ranking, and a deterministic shopping fallback for simple product questions.

Architecture:
- Derive structured shopping preferences from the latest customer message plus recent conversation turns.
- Persist those preferences in conversation metadata so follow-up messages like budget changes do not lose earlier size/color/use-case context.
- Use the structured preferences to rank catalog items more intelligently than raw text-search alone.
- When the request is a straightforward shopping question, answer deterministically or ask one clarifying question instead of defaulting to human handoff.

Tech stack: Python backend, unittest, SQLAlchemy/Postgres models, existing EasyEcom AI chat service.

Planned tasks:
1. Add failing unit tests for preference extraction and deterministic simple-shopping reply behavior.
2. Add structured preference extraction and merge logic in ai_chat_service.py.
3. Persist preference state into conversation metadata during AI context building.
4. Add constraint-aware scoring/filtering for catalog items.
5. Add deterministic shopping fallback for simple availability/recommendation/budget conversations.
6. Re-run unittest, compileall, frontend typecheck, and git diff hygiene checks.
