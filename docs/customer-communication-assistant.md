# Customer Communication Assistant

## Purpose

The customer communication assistant is a tenant-scoped sales and support layer for website chat, WhatsApp, Instagram, Facebook, Messenger, and future customer channels.

It uses NVIDIA NIM by default:

- `NVIDIA_BASE_URL=https://integrate.api.nvidia.com/v1`
- `NVIDIA_MODEL=google/gemma-4-31b-it`
- `NVIDIA_API_KEY` from deployment secrets

Do not commit provider keys. Rotate any key that was shared outside the secret store.

## Safety Model

- The model never receives raw SQL access.
- All model tools execute inside EasyEcom backend services.
- Every tool is tenant-scoped by `client_id`.
- Price and availability answers must use fresh tool results.
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

Industry templates add domain-specific questions and safety rules. For example, pet food assistants ask about pet type, age, allergies, diet, and health concerns, but they must not diagnose or replace veterinary advice.

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
