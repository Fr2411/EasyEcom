from easy_ecom.core.rbac import can_access_finance


def test_finance_access():
    assert can_access_finance(["SUPER_ADMIN"])
    assert can_access_finance(["CLIENT_OWNER"])
    assert can_access_finance(["FINANCE_ONLY"])
    assert not can_access_finance(["CLIENT_EMPLOYEE"])
