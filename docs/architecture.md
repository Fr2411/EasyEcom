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
- Customer Communication provides a tenant-safe AI assistant foundation for channel conversations, playbooks, grounded tool calls, and draft-order handoff
- `Automation` remains an intentionally blank execution module

## Rebuild rule
- New features should extend the current mounted modules and typed services instead of reviving deleted legacy paths
