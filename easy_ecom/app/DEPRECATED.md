# Deprecated Streamlit Frontend

The Streamlit UI under `easy_ecom/app/` is now **deprecated** as a product frontend.

- Active product UI development has moved to the Next.js application in `frontend/`.
- Streamlit files are retained temporarily to protect existing business logic while API and frontend migration continues.
- Do not add new product-facing UI features in Streamlit pages unless required for emergency maintenance.

Migration target: AWS Amplify-hosted Next.js frontend + FastAPI backend.
