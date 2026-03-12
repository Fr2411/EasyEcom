# AGENTS.md

## Scope

This folder owns AI-facing retrieval, channel integrations, prompt orchestration, and customer communication logic.

---

## Rules

- AI must only access tenant-authorized data.
- Availability checks must use real variant-level stock data.
- Recommendations must respect active product status, tenant catalog boundaries, and approved pricing rules.
- Do not let AI promise unavailable stock.
- Do not let AI use stale or ambiguous product records when a precise variant match is required.

---

## Sales Guidance Direction

AI should support:
- availability lookup
- product recommendation
- upsell / cross-sell
- discount-aware suggestions
- non-moving stock promotion
- revenue optimization

But correctness comes before persuasion.
