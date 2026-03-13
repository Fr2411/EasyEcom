from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app
from easy_ecom.data.store.postgres_db import Base
from easy_ecom.data.store.postgres_models import InventoryTxnModel, ProductModel, ProductVariantModel
from easy_ecom.domain.services.reports_api_service import ReportsApiService


class DummyReportsService:
    def build_filters(self, **kwargs):
        from_date = kwargs.get('from_date')
        to_date = kwargs.get('to_date')
        if from_date and to_date and from_date > to_date:
            raise ValueError('from_date must be <= to_date')
        return kwargs

    def sales_report(self, *, client_id: str, filters):
        if client_id == 'tenant-a':
            return {
                'from_date': '2026-01-01', 'to_date': '2026-01-31', 'sales_count': 1, 'revenue_total': 120,
                'sales_trend': [{'period': '2026-01-10', 'value': 120}],
                'top_products': [{'product_id': 'prd-1', 'product_name': 'Product A', 'qty_sold': 2, 'revenue': 120}],
                'top_customers': [{'customer_id': 'cus-1', 'customer_name': 'A', 'sales_count': 1, 'revenue': 120}],
                'deferred_metrics': [],
            }
        return {'from_date': '2026-01-01', 'to_date': '2026-01-31', 'sales_count': 0, 'revenue_total': 0, 'sales_trend': [], 'top_products': [], 'top_customers': [], 'deferred_metrics': []}

    def inventory_report(self, *, client_id: str, filters):
        return {
            'from_date': '2026-01-01', 'to_date': '2026-01-31', 'total_skus_with_stock': 0, 'total_stock_units': 0,
            'low_stock_items': [], 'variant_stock_rows': [], 'product_stock_rollups': [],
            'stock_movement_trend': [], 'inventory_value': None,
            'deferred_metrics': [{'metric': 'inventory_value', 'reason': 'deferred'}],
        }

    def products_report(self, *, client_id: str, filters):
        return {'from_date': '2026-01-01', 'to_date': '2026-01-31', 'highest_selling': [], 'low_or_zero_movement': [], 'deferred_metrics': []}

    def finance_report(self, *, client_id: str, filters):
        return {
            'from_date': '2026-01-01', 'to_date': '2026-01-31', 'expense_total': 30, 'expense_trend': [],
            'receivables_total': 10, 'payables_total': 20, 'net_operating_snapshot': 90,
            'deferred_metrics': [],
        }

    def returns_report(self, *, client_id: str, filters):
        return {'from_date': '2026-01-01', 'to_date': '2026-01-31', 'returns_count': 0, 'return_qty_total': 0, 'return_amount_total': 0, 'deferred_metrics': []}

    def purchases_report(self, *, client_id: str, filters):
        return {'from_date': '2026-01-01', 'to_date': '2026-01-31', 'purchases_count': 0, 'purchases_subtotal': 0, 'purchases_trend': [], 'deferred_metrics': []}

    def overview_report(self, *, client_id: str, filters):
        return {'from_date': '2026-01-01', 'to_date': '2026-01-31', 'sales_revenue_total': 120, 'sales_count': 1, 'expense_total': 30, 'returns_total': 0, 'purchases_total': 0}


class DummyContainer:
    def __init__(self) -> None:
        self.reports_mvp = DummyReportsService()


def test_reports_requires_auth() -> None:
    client = TestClient(create_app())
    assert client.get('/reports/overview').status_code == 401


def test_reports_tenant_scoped_and_validation() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    ok = client.get('/reports/sales')
    assert ok.status_code == 200
    assert ok.json()['sales_count'] == 1

    bad = client.get('/reports/sales?from_date=2026-02-01&to_date=2026-01-01')
    assert bad.status_code == 400

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    tenant_b = client.get('/reports/sales')
    assert tenant_b.status_code == 200
    assert tenant_b.json()['sales_count'] == 0

    empty = client.get('/reports/inventory')
    assert empty.status_code == 200
    assert empty.json()['inventory_value'] is None

    app.dependency_overrides.clear()


def test_inventory_report_rolls_up_products_from_variant_stock() -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with sf() as session:
        session.add(ProductModel(product_id='prd-1', client_id='tenant-a', product_name='Shirt', category='tops', is_active='true'))
        session.add(ProductVariantModel(variant_id='var-1', client_id='tenant-a', parent_product_id='prd-1', variant_name='Size M', sku_code='SHIRT-M', is_active='true'))
        session.add(ProductVariantModel(variant_id='var-2', client_id='tenant-a', parent_product_id='prd-1', variant_name='Size L', sku_code='SHIRT-L', is_active='true'))
        session.add(ProductVariantModel(variant_id='var-3', client_id='tenant-a', parent_product_id='prd-1', variant_name='Size XL', sku_code='SHIRT-XL', is_active='false'))
        session.add(InventoryTxnModel(txn_id='t1', client_id='tenant-a', timestamp='2026-01-05T00:00:00Z', txn_type='IN', product_id='prd-1', variant_id='var-1', qty='10'))
        session.add(InventoryTxnModel(txn_id='t2', client_id='tenant-a', timestamp='2026-01-06T00:00:00Z', txn_type='OUT', product_id='prd-1', variant_id='var-1', qty='4'))
        session.add(InventoryTxnModel(txn_id='t3', client_id='tenant-a', timestamp='2026-01-07T00:00:00Z', txn_type='IN', product_id='prd-1', variant_id='var-2', qty='2'))
        session.add(InventoryTxnModel(txn_id='t4', client_id='tenant-a', timestamp='2026-01-08T00:00:00Z', txn_type='IN', product_id='prd-1', variant_id='var-3', qty='1'))
        session.commit()

    service = ReportsApiService(sf)
    filters = service.build_filters(
        from_date=None,
        to_date=None,
        product_id='',
        category='tops',
        customer_id='',
    )

    report = service.inventory_report(client_id='tenant-a', filters=filters)

    assert report['total_skus_with_stock'] == 3
    assert report['total_stock_units'] == 9.0
    assert report['product_stock_rollups'] == [
        {'product_id': 'prd-1', 'product_name': 'Shirt', 'current_qty': 9.0}
    ]

    rows_by_variant = {row['variant_id']: row for row in report['variant_stock_rows']}
    assert rows_by_variant['var-1']['current_qty'] == 6.0
    assert rows_by_variant['var-2']['current_qty'] == 2.0
    assert rows_by_variant['var-3']['current_qty'] == 1.0


def test_inventory_report_low_stock_checks_only_active_variants() -> None:
    engine = create_engine('sqlite+pysqlite:///:memory:', future=True)
    Base.metadata.create_all(engine)
    sf = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with sf() as session:
        session.add(ProductModel(product_id='prd-2', client_id='tenant-a', product_name='Sneaker', category='shoes', is_active='true'))
        session.add(ProductVariantModel(variant_id='var-4', client_id='tenant-a', parent_product_id='prd-2', variant_name='42', sku_code='SNKR-42', is_active='true'))
        session.add(ProductVariantModel(variant_id='var-5', client_id='tenant-a', parent_product_id='prd-2', variant_name='43', sku_code='SNKR-43', is_active='true'))
        session.add(ProductVariantModel(variant_id='var-6', client_id='tenant-a', parent_product_id='prd-2', variant_name='44', sku_code='SNKR-44', is_active='false'))
        session.add(InventoryTxnModel(txn_id='t5', client_id='tenant-a', timestamp='2026-01-10T00:00:00Z', txn_type='IN', product_id='prd-2', variant_id='var-4', qty='5'))
        session.add(InventoryTxnModel(txn_id='t6', client_id='tenant-a', timestamp='2026-01-10T00:00:00Z', txn_type='IN', product_id='prd-2', variant_id='var-5', qty='8'))
        session.add(InventoryTxnModel(txn_id='t7', client_id='tenant-a', timestamp='2026-01-10T00:00:00Z', txn_type='IN', product_id='prd-2', variant_id='var-6', qty='2'))
        session.commit()

    service = ReportsApiService(sf)
    filters = service.build_filters(
        from_date=None,
        to_date=None,
        product_id='',
        category='shoes',
        customer_id='',
    )

    report = service.inventory_report(client_id='tenant-a', filters=filters)
    low_variant_ids = {row['variant_id'] for row in report['low_stock_items']}

    assert low_variant_ids == {'var-4'}
