from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from sqlalchemy import func, select

from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.postgres_models import (
    ClientModel,
    ClientSettingsModel,
    CustomerModel,
    FinanceTransactionModel,
    InventoryLedgerModel,
    LocationModel,
    ProductVariantModel,
    PurchaseModel,
    SalesOrderModel,
    SalesReturnModel,
)
from easy_ecom.scripts.init_data import _seed_sample_business_data
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime


def _seed_default_client(runtime) -> tuple[str, str]:
    client_id = new_uuid()
    location_id = new_uuid()
    with runtime.session_factory() as session:
        session.add(
            ClientModel(
                client_id=client_id,
                slug="default",
                business_name="Default Client",
                contact_name="Owner",
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
                allow_backorder=False,
                default_location_name="Main Warehouse",
                require_discount_approval=False,
                order_prefix="SO",
                purchase_prefix="PO",
                return_prefix="RT",
            )
        )
        session.add(
            LocationModel(
                location_id=location_id,
                client_id=client_id,
                name="Main Warehouse",
                code="MAIN",
                is_default=True,
                status="active",
            )
        )
        session.commit()
    return client_id, location_id


def test_sample_seed_creates_cross_module_data_with_variant_ledger_integrity(tmp_path: Path) -> None:
    runtime = build_sqlite_runtime(tmp_path, "init_data_seed.db")
    client_id, location_id = _seed_default_client(runtime)

    with runtime.session_factory() as session:
        _seed_sample_business_data(
            session,
            client_id=client_id,
            location_id=location_id,
            created_by_user_id=None,
        )
        session.commit()

    with runtime.session_factory() as session:
        assert session.execute(
            select(func.count()).select_from(PurchaseModel).where(PurchaseModel.client_id == client_id)
        ).scalar_one() == 1
        assert session.execute(
            select(func.count()).select_from(ProductVariantModel).where(ProductVariantModel.client_id == client_id)
        ).scalar_one() == 6
        assert session.execute(
            select(func.count()).select_from(CustomerModel).where(CustomerModel.client_id == client_id)
        ).scalar_one() == 2
        assert session.execute(
            select(func.count()).select_from(SalesOrderModel).where(SalesOrderModel.client_id == client_id)
        ).scalar_one() == 2
        assert session.execute(
            select(func.count()).select_from(SalesReturnModel).where(SalesReturnModel.client_id == client_id)
        ).scalar_one() == 1
        assert session.execute(
            select(func.count()).select_from(FinanceTransactionModel).where(FinanceTransactionModel.client_id == client_id)
        ).scalar_one() == 4

        product_variant_ids = {
            row[0]
            for row in session.execute(
                select(ProductVariantModel.variant_id).where(ProductVariantModel.client_id == client_id)
            ).all()
        }
        ledger_variant_ids = {
            row[0]
            for row in session.execute(
                select(InventoryLedgerModel.variant_id).where(InventoryLedgerModel.client_id == client_id)
            ).all()
        }
        assert ledger_variant_ids.issubset(product_variant_ids)
        assert session.execute(
            select(func.count()).select_from(InventoryLedgerModel).where(
                InventoryLedgerModel.client_id == client_id,
                InventoryLedgerModel.quantity_delta < 0,
            )
        ).scalar_one() >= 1


def test_sample_seed_is_idempotent(tmp_path: Path) -> None:
    runtime = build_sqlite_runtime(tmp_path, "init_data_seed_idempotent.db")
    client_id, location_id = _seed_default_client(runtime)

    with runtime.session_factory() as session:
        _seed_sample_business_data(
            session,
            client_id=client_id,
            location_id=location_id,
            created_by_user_id=None,
        )
        session.commit()

    with runtime.session_factory() as session:
        _seed_sample_business_data(
            session,
            client_id=client_id,
            location_id=location_id,
            created_by_user_id=None,
        )
        session.commit()

    with runtime.session_factory() as session:
        assert session.execute(
            select(func.count()).select_from(PurchaseModel).where(PurchaseModel.client_id == client_id)
        ).scalar_one() == 1
        assert session.execute(
            select(func.count()).select_from(SalesOrderModel).where(SalesOrderModel.client_id == client_id)
        ).scalar_one() == 2
        assert session.execute(
            select(func.count()).select_from(FinanceTransactionModel).where(FinanceTransactionModel.client_id == client_id)
        ).scalar_one() == 4
