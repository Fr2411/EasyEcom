# AWS Target Architecture

## Preserved connectivity
- Frontend hosting path: AWS Amplify
- Backend deployment path remains EC2-based through the repo's operational flow
- Database: AWS RDS PostgreSQL
- Secrets/config: environment variables injected by the existing deployment setup

## Current app scope
1. Amplify-hosted frontend calls the FastAPI backend.
2. FastAPI serves auth, session, health, public webhook, and mounted business routers for the commerce/admin stack.
3. PostgreSQL stores auth-core tables plus tenant-scoped commerce, channel, and audit tables.
4. `init_data.py` can seed a clean super-admin and tenant defaults into the preserved RDS connection.
5. `Automation` is the remaining placeholder module.

## Reset boundary
- Infrastructure resources and connectivity are preserved.
- The app is no longer auth-core-only. Core business modules are already live, so future work should be treated as incremental production work rather than a rebuild from scratch.
