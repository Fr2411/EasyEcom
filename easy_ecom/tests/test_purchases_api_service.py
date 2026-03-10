from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from easy_ecom.data.store.postgres_db import Base
from easy_ecom.data.store.postgres_models import (
    FinanceExpenseModel,
    InventoryTxnModel,
    ProductModel,
    PurchaseItemModel,
    PurchaseModel,
    SupplierModel,
    TenantSettingsModel,
)
from easy_ecom.domain.services.purchases_api_service import (
    PurchaseCreateInput,
    PurchaseLineInput,
    PurchasesApiService,
)


def _service():
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    return PurchasesApiService(factory), factory


def _seed(factory):
    with factory() as session:
        session.add(TenantSettingsModel(client_id='tenant-a', purchases_prefix='BUY'))
        session.add(ProductModel(product_id='prd-1', client_id='tenant-a', product_name='Paper', is_active='true'))
        session.add(ProductModel(product_id='prd-2', client_id='tenant-b', product_name='Other', is_active='true'))
        session.add(SupplierModel(supplier_id='sup-1', client_id='tenant-a', name='Main Supplier', is_active='true'))
        session.commit()


def test_create_purchase_updates_inventory_and_finance() -> None:
    service, factory = _service()
    _seed(factory)

    result = service.create_purchase(
        client_id='tenant-a',
        user_id='u-1',
        payload=PurchaseCreateInput(
            purchase_date='2026-03-14',
            supplier_id='sup-1',
            reference_no='INV-77',
            note='stock in',
            payment_status='unpaid',
            lines=[PurchaseLineInput(product_id='prd-1', qty=3, unit_cost=12.5)],
        ),
    )

    assert result['purchase_no'].startswith('BUY-')

    with factory() as session:
        purchase = session.execute(select(PurchaseModel).where(PurchaseModel.client_id == 'tenant-a')).scalar_one()
        lines = session.execute(select(PurchaseItemModel).where(PurchaseItemModel.purchase_id == purchase.purchase_id)).scalars().all()
        txns = session.execute(select(InventoryTxnModel).where(InventoryTxnModel.source_id == purchase.purchase_id)).scalars().all()
        expense = session.execute(select(FinanceExpenseModel).where(FinanceExpenseModel.client_id == 'tenant-a')).scalar_one()

    assert len(lines) == 1
    assert len(txns) == 1
    assert txns[0].txn_type == 'IN'
    assert txns[0].source_type == 'purchase'
    assert expense.category == 'Purchases'
    assert expense.payment_status == 'unpaid'


def test_create_purchase_rejects_cross_tenant_product() -> None:
    service, factory = _service()
    _seed(factory)

    try:
        service.create_purchase(
            client_id='tenant-a',
            user_id='u-1',
            payload=PurchaseCreateInput(
                purchase_date='2026-03-14',
                supplier_id='',
                reference_no='',
                note='',
                payment_status='paid',
                lines=[PurchaseLineInput(product_id='prd-2', qty=1, unit_cost=3)],
            ),
        )
    except ValueError as exc:
        assert 'Invalid product reference' in str(exc)
    else:
        raise AssertionError('expected ValueError')
