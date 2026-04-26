# Customer Communication Assistant

## Purpose

The customer communication assistant is a tenant-scoped sales and support layer for website chat, WhatsApp, Instagram, Facebook, Messenger, and future customer channels.

It uses an OpenAI-compatible chat-completions API. NVIDIA NIM is the default deployment target:

- `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
- `NVIDIA_MODEL=google/gemma-4-31b-it`
- `NVIDIA_FALLBACK_MODEL=nvidia/nemotron-3-super-120b-a12b`
- `NVIDIA_API_KEY` from deployment secrets

Set `AI_PROVIDER=openai` to use the existing OpenAI settings instead:

- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_MODEL=gpt-4o-mini`
- `OPENAI_API_KEY` from deployment secrets

Do not commit provider keys. Rotate any key that was shared outside the secret store.

For NVIDIA, Gemma remains the primary model and Nemotron is the bounded fallback for transient timeout/network/provider failures before escalating the conversation.

The assistant does not use canned customer-facing sales replies. The backend builds a tenant-safe reply context from the playbook, memory graph, live catalog tools, variant-level availability, pricing, policies, and draft-order state. The model then composes the outbound customer message from that context. Deterministic backend code is reserved for selecting safe facts, enforcing tenant boundaries, creating draft orders, marking escalations, and validating the model output. Static text is used only as a last-resort failure fallback when the model cannot produce a safe reply.

The composer also retries once if a provider returns internal reasoning or source-context commentary instead of a final customer reply. If the retry still exposes reasoning, validation blocks the response and escalates rather than sending it to the customer.

## Safety Model

- The model never receives raw SQL access.
- EasyEcom backend services gather all live facts before composition.
- Every fact-gathering tool is tenant-scoped by `client_id`.
- Price and availability answers must use fresh backend tool results.
- Availability is resolved from variant-level ledger and reservation totals.
- Draft order creation is allowed only as `draft`; confirmation, fulfillment, payment, and stock mutation remain staff-controlled.

## Tenant Playbook

Each tenant has a structured assistant playbook:

- business type
- brand personality
- custom instructions
- forbidden claims
- sales goals
- delivery, returns, payment, warranty, and discount policies
- escalation rules
- industry template guidance

Industry templates add domain-specific questions and safety rules. For example, pet food assistants ask about pet type, age, allergies, diet, and health concerns, but they must not diagnose or replace veterinary advice. Shoe store assistants ask for shoe size, intended use, color or style, fit preference, and budget before recommending or checking exact variants.

## Business Owner Knowledge Base

The first knowledge-base layer is the tenant playbook: business type, brand voice, policies, forbidden claims, sales goals, and escalation rules. This lets the assistant answer like a trained owner or senior sales person without moving operational truth into prompts.

Graphify remains useful for developer and operator knowledge. Run it against docs, SOPs, and architecture notes to produce `GRAPH_REPORT.md` and `graph.json`, then use those outputs to refine playbook instructions and support scripts. Do not use Graphify output as the source of truth for live stock, price, orders, or tenant permissions; those must continue to come from backend tools.

## Conversation Records

The system stores:

- channel accounts
- conversations
- inbound and outbound messages
- assistant runs
- tool calls and summarized tool results
- escalation state
- draft order links

Provider adapters normalize all channels into the same conversation model so assistant behavior stays consistent across channels.
