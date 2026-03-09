from pathlib import Path
from types import SimpleNamespace

from easy_ecom.data.repos.csv.users_repo import RolesRepo, UserRolesRepo, UsersRepo
from easy_ecom.data.store.csv_store import CsvStore
from easy_ecom.data.store.schema import TABLE_SCHEMAS
from easy_ecom.domain.models.user import UserCreate
from easy_ecom.domain.services.user_service import UserService


def setup_store(tmp_path: Path) -> CsvStore:
    store = CsvStore(tmp_path)
    for table_name, columns in TABLE_SCHEMAS.items():
        store.ensure_table(table_name, columns)
    return store


def test_user_password_is_stored_as_hash(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = UserService(UsersRepo(store), RolesRepo(store), UserRolesRepo(store))

    user_id = svc.create(
        UserCreate(
            client_id="c1",
            name="Alice",
            email="not-an-email",
            password="my-secret",
            role_code="CLIENT_OWNER",
        )
    )

    users_df = UsersRepo(store).all()
    saved = users_df[users_df["user_id"] == user_id].iloc[0]
    assert saved["password"] == ""
    assert str(saved["password_hash"]).startswith("$2")


def test_only_super_admin_can_login_from_csv(tmp_path: Path):
    store = setup_store(tmp_path)
    svc = UserService(UsersRepo(store), RolesRepo(store), UserRolesRepo(store))

    svc.create(
        UserCreate(
            client_id="c1",
            name="Alice",
            email="owner@example.com",
            password="my-secret",
            role_code="CLIENT_OWNER",
        )
    )

    result = svc.login("owner@example.com", "my-secret")
    assert result is None


def test_super_admin_can_login_even_without_users_csv_data(tmp_path: Path, monkeypatch):
    from easy_ecom.domain.services import user_service as user_service_module

    monkeypatch.setattr(
        user_service_module,
        "settings",
        SimpleNamespace(super_admin_email="super@example.com", super_admin_password="super-secret"),
    )

    store = setup_store(tmp_path)
    svc = UserService(UsersRepo(store), RolesRepo(store), UserRolesRepo(store))

    result = svc.login("super@example.com", "super-secret")
    assert result is not None
    assert result["roles"] == "SUPER_ADMIN"
    assert result["user_id"] == "ENV_SUPER_ADMIN"
