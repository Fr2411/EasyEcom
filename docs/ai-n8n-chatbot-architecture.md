# AI n8n Chatbot Architecture

## Boundary

EasyEcom owns tenant safety, durable memory, policy, product data, variant-level availability, pricing, order confirmation, and audit logs. n8n owns LLM orchestration and customer reply composition.

n8n workflows must not query PostgreSQL directly. Use the protected `/ai/tools/*` endpoints with the `X-EasyEcom-AI-Tool-Token` header.

## Website Chat Flow

1. Tenant configures AI Agent settings in EasyEcom Settings.
2. Tenant embeds the generated widget script on an allowed website origin.
3. The widget posts customer messages to `/ai/chat/public/{widget_key}/messages`.
4. EasyEcom validates widget key, origin, rate limit, and conversation session.
5. EasyEcom stores the inbound message and sends n8n the conversation payload.
6. n8n calls EasyEcom tool APIs for context, catalog search, stock checks, handoff, or order confirmation.
7. EasyEcom stores the outbound reply and returns it to the widget.

## Order Confirmation Rules

The n8n workflow may call `/ai/tools/orders/confirm-from-chat`, but EasyEcom enforces:

- explicit customer confirmation
- customer name, phone, and delivery address
- variant-level stock validation through existing sales confirmation logic
- unpaid/COD payment status
- pending shipment status
- source channel and conversation references on the sales order

The AI tool never fulfills, refunds, or records payment.
