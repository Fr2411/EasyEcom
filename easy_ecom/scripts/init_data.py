from __future__ import annotations

from sqlalchemy import select

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import ClientModel, RoleModel, UserModel, UserRoleModel
from easy_ecom.data.store.schema import ROLES_SEED


def main() -> None:
    engine = build_postgres_engine(settings)
    init_postgres_schema(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        for role in ROLES_SEED:
            existing_role = session.execute(
                select(RoleModel).where(RoleModel.role_code == role["role_code"])
            ).scalar_one_or_none()
            if existing_role is None:
                session.add(RoleModel(**role))

        admin_email = settings.super_admin_email.strip().lower()
        admin_password = settings.super_admin_password
        if admin_email and admin_password:
            existing_user = session.execute(
                select(UserModel).where(UserModel.email == admin_email)
            ).scalar_one_or_none()
            if existing_user is None:
                admin_id = new_uuid()
                session.add(
                    UserModel(
                        user_id=admin_id,
                        client_id="GLOBAL",
                        name="Super Admin",
                        email=admin_email,
                        password="",
                        password_hash=hash_password(admin_password),
                        is_active="true",
                        created_at=now_iso(),
                    )
                )
                session.add(UserRoleModel(user_id=admin_id, role_code="SUPER_ADMIN"))

        if settings.create_default_client:
            existing_client = session.execute(
                select(ClientModel).where(ClientModel.client_id == "DEFAULT")
            ).scalar_one_or_none()
            if existing_client is None:
                session.add(
                    ClientModel(
                        client_id="DEFAULT",
                        business_name="Default Client",
                        owner_name="Owner",
                        phone="",
                        email="owner@example.com",
                        address="",
                        currency_code="USD",
                        currency_symbol="$",
                        website_url="",
                        facebook_url="",
                        instagram_url="",
                        whatsapp_number="",
                        created_at=now_iso(),
                        status="active",
                        notes="",
                    )
                )

        session.commit()


if __name__ == "__main__":
    main()
