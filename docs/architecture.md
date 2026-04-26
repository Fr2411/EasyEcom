# Architecture Direction

## Current foundation
- Frontend shell: Next.js app in `frontend/` with production workspaces for dashboard, catalog, inventory, purchases, sales, returns, finance, reports, integrations, sales agent, AI review, admin, and settings
- Backend shell: FastAPI service in `easy_ecom/api` mounting auth, session, health, public webhook, and business routers
- Runtime data source: PostgreSQL through `DATABASE_URL`
- Bootstrap: `easy_ecom/scripts/init_data.py` seeds roles and an optional super-admin

## Preserved infrastructure contracts
- Amplify remains the frontend hosting path
- EC2-backed deployment wiring remains preserved in repo scripts
- RDS remains the database boundary
- Existing env var names and startup entrypoints stay stable during the rebuild

## Current product boundary
- Core commerce workflows are active and variant-first for inventory, sales, returns, and purchases
- Customer access is currently embedded inside transaction flows rather than exposed as a standalone CRM shell
- `Automation` remains the last intentionally blank module

## AI customer communication boundary
- EasyEcom is the tenant-safe commerce brain for AI chat: policy, durable memory, tool-call audit, product lookup, variant availability, and order confirmation live in FastAPI/PostgreSQL.
- n8n is the orchestration layer for LLM flow and channel workflow. It must call EasyEcom AI tool APIs instead of querying PostgreSQL directly.
- Website chat is the first supported public channel through an embeddable widget key. WhatsApp/Messenger should attach to the same AI tool boundary later rather than reintroducing the removed legacy channel schema.
- AI-created orders may be confirmed automatically only through the backend order tool, which reuses variant-level stock validation and records source conversation/channel references.

## Rebuild rule
- New features should extend the current mounted modules and typed services instead of reviving deleted legacy paths
