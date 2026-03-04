from easy_ecom.data.repos.base import BaseRepo


class AuditRepo(BaseRepo):
    table_name = "audit_log.csv"
