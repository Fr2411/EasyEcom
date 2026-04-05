# Finance Access Matrix

This matrix defines Finance page visibility after `FAZ-37`.

## Rule Summary

- Finance access is role-gated first.
- Subscription tier must not remove Finance access for otherwise authorized roles.
- Tenant isolation and normal API authorization still apply.

## Visibility Matrix

| Role | Free plan | Growth plan | Scale plan |
|---|---|---|---|
| `SUPER_ADMIN` | Allowed | Allowed | Allowed |
| `CLIENT_OWNER` | Allowed | Allowed | Allowed |
| `FINANCE_STAFF` | Allowed | Allowed | Allowed |
| `CLIENT_STAFF` | Denied | Denied | Denied |

## Notes

- No migration is required for this change.
- No tenant data model changes are introduced.
- Backend remains the source of truth via `allowed_pages` + `require_page_access`.
