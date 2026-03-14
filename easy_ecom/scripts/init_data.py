from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.data.store.migrations import apply_sql_migrations
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import (
    ClientModel,
    ClientSettingsModel,
    LocationModel,
    RoleModel,
    UserModel,
    UserRoleModel,
)
from easy_ecom.data.store.schema import ROLES_SEED


def _bootstrap_schema(engine) -> None:
    if settings.is_sqlite:
        init_postgres_schema(engine)
        return
    apply_sql_migrations(engine)


def main() -> None:
    engine = build_postgres_engine(settings)
    _bootstrap_schema(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        global_client = session.execute(
            select(ClientModel).where(ClientModel.client_id == settings.global_client_id)
        ).scalar_one_or_none()
        if global_client is None:
            session.add(
                ClientModel(
                    client_id=settings.global_client_id,
                    slug=settings.global_client_slug,
                    business_name="EasyEcom Global",
                    owner_name="EasyEcom",
                    email=settings.super_admin_email.strip().lower(),
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    status="active",
                )
            )

        for role in ROLES_SEED:
            existing_role = session.execute(
                select(RoleModel).where(RoleModel.role_code == role["role_code"])
            ).scalar_one_or_none()
            if existing_role is None:
                session.add(RoleModel(**role))

        existing_settings = session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == settings.global_client_id)
        ).scalar_one_or_none()
        if existing_settings is None:
            session.add(
                ClientSettingsModel(
                    client_settings_id=new_uuid(),
                    client_id=settings.global_client_id,
                    low_stock_threshold=Decimal("5"),
                    allow_backorder=settings.allow_backorder,
                    default_location_name="Global Warehouse",
                    require_discount_approval=False,
                    order_prefix="SO",
                    purchase_prefix="PO",
                    return_prefix="RT",
                )
            )

        existing_location = session.execute(
            select(LocationModel).where(
                LocationModel.client_id == settings.global_client_id,
                LocationModel.code == "GLOBAL",
            )
        ).scalar_one_or_none()
        if existing_location is None:
            session.add(
                LocationModel(
                    location_id=new_uuid(),
                    client_id=settings.global_client_id,
                    name="Global Warehouse",
                    code="GLOBAL",
                    is_default=True,
                    status="active",
                )
            )

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
                        client_id=settings.global_client_id,
                        name="Super Admin",
                        email=admin_email,
                        password="",
                        password_hash=hash_password(admin_password),
                        is_active=True,
                    )
                )
                session.add(UserRoleModel(user_id=admin_id, role_code="SUPER_ADMIN"))

        if settings.create_default_client:
            default_slug = "default"
            existing_client = session.execute(
                select(ClientModel).where(ClientModel.slug == default_slug)
            ).scalar_one_or_none()
            if existing_client is None:
                client_id = new_uuid()
                session.add(
                    ClientModel(
                        client_id=client_id,
                        slug=default_slug,
                        business_name="Default Client",
                        owner_name="Owner",
                        email="owner@example.com",
                        currency_code="USD",
                        currency_symbol="$",
                        timezone="UTC",
                        status="active",
                    )
                )
                session.add(
                    ClientSettingsModel(
                        client_settings_id=new_uuid(),
                        client_id=client_id,
                        low_stock_threshold=Decimal("5"),
                        allow_backorder=settings.allow_backorder,
                        default_location_name="Main Warehouse",
                        require_discount_approval=False,
                        order_prefix="SO",
                        purchase_prefix="PO",
                        return_prefix="RT",
                    )
                )
                session.add(
                    LocationModel(
                        location_id=new_uuid(),
                        client_id=client_id,
                        name="Main Warehouse",
                        code="MAIN",
                        is_default=True,
                        status="active",
                    )
                )

        session.commit()


if __name__ == "__main__":
    main()
