# AWS Target Architecture

## Preserved connectivity
- Frontend hosting path: AWS Amplify
- Backend deployment path currently preserved through the repo's EC2-based operational flow
- Database: AWS RDS PostgreSQL
- Secrets/config: environment variables injected by the existing deployment setup

## Current app scope
1. Amplify-hosted frontend calls the FastAPI backend.
2. FastAPI serves only auth, session, and health endpoints.
3. PostgreSQL stores auth-core tables only: `clients`, `users`, `roles`, `user_roles`.
4. `init_data.py` can seed a clean super-admin into the preserved RDS connection.

## Reset boundary
- Infrastructure resources and connectivity are preserved.
- Business tables, business logic, and business UI content are intentionally removed until rebuilt.
