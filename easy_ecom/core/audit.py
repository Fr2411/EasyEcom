from __future__ import annotations

import json
from typing import Any

from easy_ecom.core.ids import new_uuid
from easy_ecom.core.time_utils import now_iso
from easy_ecom.data.repos.csv.audit_repo import AuditRepo


def log_event(
    repo: AuditRepo,
    user_id: str,
    client_id: str,
    action: str,
    entity_type: str,
    entity_id: str,
    details: dict[str, Any],
) -> None:
    repo.append(
        {
            "event_id": new_uuid(),
            "timestamp": now_iso(),
            "user_id": user_id,
            "client_id": client_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "details_json": json.dumps(details),
        }
    )
