from pathlib import Path

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


def test_user_password_is_stored_in_plain_text_and_login_supports_it(tmp_path: Path):
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
    assert saved["password"] == "my-secret"

    result = svc.login("not-an-email", "my-secret")
    assert result is not None
    assert result["user_id"] == user_id
