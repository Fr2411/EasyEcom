# AI Native Chatbot Architecture

## Boundary

EasyEcom owns tenant safety, durable memory, approved policy, product data, variant-level availability, pricing, order confirmation, AI model orchestration, and audit logs.

The AI model must not query PostgreSQL or external business systems directly. EasyEcom assembles a tenant-scoped prompt from approved settings, recent conversation memory, customer details, and minimal live catalog facts derived through backend service methods.

## Website Chat Flow

1. Tenant configures AI Assistant settings in EasyEcom Settings.
2. Tenant embeds the generated widget script, or shares the generated customer chat link.
3. The public chat surface posts customer messages to `/ai/chat/public/{widget_key}/messages`.
4. EasyEcom validates widget key, origin, rate limit, and conversation session.
5. EasyEcom stores the inbound message.
6. EasyEcom prepares tenant-scoped context from profile policy, FAQ, recent messages, customer details, and variant-level stock/pricing facts.
7. EasyEcom calls the configured AI model API using `OPENAI_API_KEY`, `OPENAI_MODEL`, and `OPENAI_BASE_URL`.
8. EasyEcom parses the model's JSON response/action contract, enforces backend guardrails, records tool/model audit rows, stores the outbound reply, and returns it to the chat surface.

## Model Response Contract

The model returns one JSON object:

```json
{
  "reply_text": "Customer-facing answer",
  "handoff_required": false,
  "handoff_reason": "",
  "latest_intent": "availability",
  "latest_summary": "Customer asked about EU42 running shoes.",
  "action": { "type": "none" }
}
```

Supported actions are `none`, `handoff`, and `confirm_order`. Any unsupported or invalid action becomes a handoff.

## Order Confirmation Rules

The model may request `confirm_order`, but EasyEcom enforces:

- explicit customer confirmation
- customer name, phone, and delivery address
- variant-level stock validation through existing sales confirmation logic
- tenant pricing and minimum price validation
- unpaid/COD payment status
- pending shipment status
- source channel and conversation references on the sales order

The AI path never fulfills, refunds, cancels, or records payment automatically.
