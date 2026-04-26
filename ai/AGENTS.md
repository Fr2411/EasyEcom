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
- n8n workflows must use EasyEcom AI tool APIs and must not query tenant tables directly.
- Public chat widgets must validate widget key, origin, conversation session, and rate limits before invoking n8n.

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

## n8n Boundary

EasyEcom owns durable conversation state, policy, customer/order data, stock truth, and tool-call audit logs. n8n owns orchestration and LLM prompting only. Any order confirmation must go through the EasyEcom order tool so stock reservation and pricing checks remain backend-enforced.
