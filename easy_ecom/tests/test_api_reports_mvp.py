from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


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
            'low_stock_items': [], 'stock_movement_trend': [], 'inventory_value': None,
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
