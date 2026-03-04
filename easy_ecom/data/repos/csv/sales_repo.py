from easy_ecom.data.repos.base import BaseRepo


class SalesOrdersRepo(BaseRepo):
    table_name = "sales_orders.csv"


class SalesOrderItemsRepo(BaseRepo):
    table_name = "sales_order_items.csv"


class InvoicesRepo(BaseRepo):
    table_name = "invoices.csv"


class ShipmentsRepo(BaseRepo):
    table_name = "shipments.csv"


class PaymentsRepo(BaseRepo):
    table_name = "payments.csv"
