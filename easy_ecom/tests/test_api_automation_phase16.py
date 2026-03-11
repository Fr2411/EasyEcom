from __future__ import annotations

from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyAutomationService:
    def __init__(self) -> None:
        self.policies = {
            "tenant-a": {
                "policy_id": "p-a",
                "client_id": "tenant-a",
                "automation_enabled": True,
                "auto_send_enabled": False,
                "emergency_disabled": False,
                "categories": {
                    "product_availability": True,
                    "stock_availability": True,
                    "simple_price_inquiry": True,
                    "business_hours_basic_info": False,
                },
                "updated_by_user_id": "u1",
                "created_at": "",
                "updated_at": "",
            },
            "tenant-b": {
                "policy_id": "p-b",
                "client_id": "tenant-b",
                "automation_enabled": False,
                "auto_send_enabled": False,
                "emergency_disabled": False,
                "categories": {
                    "product_availability": True,
                    "stock_availability": True,
                    "simple_price_inquiry": True,
                    "business_hours_basic_info": False,
                },
                "updated_by_user_id": "u2",
                "created_at": "",
                "updated_at": "",
            },
        }
        self.history = {"tenant-a": [], "tenant-b": []}

    def get_policy(self, *, client_id: str):
        return self.policies[client_id]

    def patch_policy(self, *, client_id: str, updated_by_user_id: str, payload):
        row = self.policies[client_id]
        if payload.automation_enabled is not None:
            row["automation_enabled"] = payload.automation_enabled
        if payload.auto_send_enabled is not None:
            row["auto_send_enabled"] = payload.auto_send_enabled
        if payload.categories:
            row["categories"].update(payload.categories)
        row["updated_by_user_id"] = updated_by_user_id
        return row

    def enable(self, *, client_id: str, updated_by_user_id: str):
        self.policies[client_id]["automation_enabled"] = True
        self.policies[client_id]["updated_by_user_id"] = updated_by_user_id
        return self.policies[client_id]

    def disable(self, *, client_id: str, updated_by_user_id: str, emergency: bool = False):
        self.policies[client_id]["automation_enabled"] = False
        self.policies[client_id]["emergency_disabled"] = emergency
        self.policies[client_id]["updated_by_user_id"] = updated_by_user_id
        return self.policies[client_id]

    def evaluate(self, *, client_id: str, conversation_id: str):
        if conversation_id == "conv-unknown":
            raise ValueError("Conversation not found")
        if client_id == "tenant-a" and conversation_id == "conv-1":
            return {
                "conversation_id": conversation_id,
                "inbound_message_id": "msg-1",
                "category": "simple_price_inquiry",
                "classification_rule": "keyword_price",
                "automation_eligible": True,
                "recommended_action": "draft_for_review",
                "reason": "eligible_low_risk",
                "candidate_reply": "Current listed prices are...",
                "intent": "pricing_lookup",
                "confidence": "insufficient_context",
                "grounding": {},
            }
        return {
            "conversation_id": conversation_id,
            "inbound_message_id": "msg-2",
            "category": "unsupported",
            "classification_rule": "no_low_risk_rule_match",
            "automation_eligible": False,
            "recommended_action": "human_review",
            "reason": "unsupported_or_ambiguous",
        }

    def run(self, *, client_id: str, conversation_id: str, run_by_user_id: str):
        if conversation_id == "conv-unknown":
            raise ValueError("Conversation not found")
        row = {
            "decision_id": f"d-{client_id}-{conversation_id}",
            "conversation_id": conversation_id,
            "inbound_message_id": "msg-1",
            "policy_id": self.policies[client_id]["policy_id"],
            "category": "simple_price_inquiry",
            "classification_rule": "keyword_price",
            "recommended_action": "draft_for_review",
            "outcome": "drafted",
            "reason": "eligible_low_risk",
            "confidence": "insufficient_context",
            "candidate_reply": "Current listed prices are...",
            "audit_context": {"evaluation": {"conversation_id": conversation_id}},
            "run_by_user_id": run_by_user_id,
            "created_at": "",
            "updated_at": "",
        }
        self.history[client_id].append(row)
        return row

    def list_history(self, *, client_id: str, limit: int = 100):
        return self.history[client_id][:limit]

    def list_queue(self, *, client_id: str, limit: int = 100):
        return [row for row in self.history[client_id] if row["outcome"] in {"drafted", "escalated", "failed"}][:limit]


class DummyContainer:
    def __init__(self) -> None:
        self.automation = DummyAutomationService()


def test_automation_requires_authentication() -> None:
    client = TestClient(create_app())
    resp = client.get('/automation/policies')
    assert resp.status_code == 401


def test_automation_access_control_and_tenant_isolation() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    ok = client.get('/automation/policies')
    assert ok.status_code == 200
    assert ok.json()['client_id'] == 'tenant-a'

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    other = client.get('/automation/policies')
    assert other.status_code == 200
    assert other.json()['client_id'] == 'tenant-b'

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u3', client_id='tenant-a', roles=['CLIENT_EMPLOYEE'])
    forbidden = client.get('/automation/policies')
    assert forbidden.status_code == 403

    app.dependency_overrides.clear()


def test_automation_enable_disable_evaluate_run_history() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_MANAGER'])
    client = TestClient(app)

    disable = client.post('/automation/disable', json={'emergency': True})
    assert disable.status_code == 200
    assert disable.json()['automation_enabled'] is False
    assert disable.json()['emergency_disabled'] is True

    enable = client.post('/automation/enable')
    assert enable.status_code == 200
    assert enable.json()['automation_enabled'] is True

    eval_ok = client.post('/automation/evaluate/conv-1')
    assert eval_ok.status_code == 200
    assert eval_ok.json()['automation_eligible'] is True

    eval_bad = client.post('/automation/evaluate/conv-unknown')
    assert eval_bad.status_code == 400

    run = client.post('/automation/run/conv-1')
    assert run.status_code == 200
    assert run.json()['outcome'] == 'drafted'

    history = client.get('/automation/history')
    assert history.status_code == 200
    assert len(history.json()['items']) == 1

    queue = client.get('/automation/queue')
    assert queue.status_code == 200
    assert queue.json()['items'][0]['outcome'] == 'drafted'

    app.dependency_overrides.clear()
