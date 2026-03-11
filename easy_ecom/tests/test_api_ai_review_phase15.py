from __future__ import annotations

from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyAiReviewService:
    def __init__(self) -> None:
        self.conversations = {
            "tenant-a": [{"conversation_id": "conv-1", "channel_id": "chl-1", "external_sender_id": "wa-1", "customer_id": None, "status": "new", "last_message_at": "2026-03-10T10:00:00Z", "preview_message_id": "msg-in-1", "preview_text": "price?"}],
            "tenant-b": [],
        }
        self.drafts = {
            "tenant-a": {"d-1": {"draft_id": "d-1", "conversation_id": "conv-1", "inbound_message_id": "msg-in-1", "status": "draft_created", "ai_draft_text": "Draft", "edited_text": "", "final_text": "", "intent": "pricing_lookup", "confidence": "grounded", "grounding": {}, "requested_by_user_id": "u1", "approved_by_user_id": None, "sent_by_user_id": None, "created_at": "", "updated_at": "", "approved_at": None, "sent_at": None, "failed_reason": None, "send_result": {}, "human_modified": False}},
            "tenant-b": {},
        }

    def list_review_conversations(self, *, client_id: str, limit: int = 50):
        return self.conversations.get(client_id, [])[:limit]

    def get_review_conversation(self, *, client_id: str, conversation_id: str):
        if client_id == "tenant-a" and conversation_id == "conv-1":
            return {"conversation_id": "conv-1", "channel_id": "chl-1", "external_sender_id": "wa-1", "status": "open", "messages": [{"message_id": "msg-in-1", "direction": "inbound", "message_text": "price?", "content_summary": "price?", "occurred_at": "", "outbound_status": "received"}], "latest_draft": self.drafts["tenant-a"]["d-1"]}
        return None

    def create_draft(self, *, client_id: str, requested_by_user_id: str, payload):
        if payload.conversation_id != "conv-1":
            raise ValueError("Inbound message not found")
        return self.drafts[client_id]["d-1"]

    def edit_draft(self, *, client_id: str, draft_id: str, payload):
        row = self.drafts[client_id].get(draft_id)
        if row is None:
            raise ValueError("Draft not found")
        row["edited_text"] = payload.edited_text
        row["status"] = "edited"
        return row

    def approve_draft(self, *, client_id: str, draft_id: str, approved_by_user_id: str):
        row = self.drafts[client_id].get(draft_id)
        if row is None:
            raise ValueError("Draft not found")
        row["status"] = "approved"
        row["approved_by_user_id"] = approved_by_user_id
        row["final_text"] = row["edited_text"] or row["ai_draft_text"]
        return row

    def reject_draft(self, *, client_id: str, draft_id: str, rejected_by_user_id: str):
        row = self.drafts[client_id].get(draft_id)
        if row is None:
            raise ValueError("Draft not found")
        row["status"] = "rejected"
        return row

    def send_draft(self, *, client_id: str, draft_id: str, sent_by_user_id: str):
        row = self.drafts[client_id].get(draft_id)
        if row is None:
            raise ValueError("Draft not found")
        if row["status"] != "approved":
            raise ValueError("Draft must be approved before sending")
        row["status"] = "sent"
        row["sent_by_user_id"] = sent_by_user_id
        row["send_result"] = {"status": "prepared"}
        return row

    def list_history(self, *, client_id: str, limit: int = 100):
        return list(self.drafts.get(client_id, {}).values())[:limit]


class DummyContainer:
    def __init__(self) -> None:
        self.ai_review = DummyAiReviewService()


def test_ai_review_requires_authentication() -> None:
    client = TestClient(create_app())
    resp = client.get('/ai/review/conversations')
    assert resp.status_code == 401


def test_ai_review_access_control_and_tenant_isolation() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    ok = client.get('/ai/review/conversations')
    assert ok.status_code == 200
    assert len(ok.json()['items']) == 1

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    other = client.get('/ai/review/conversations')
    assert other.status_code == 200
    assert other.json()['items'] == []

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u3', client_id='tenant-a', roles=['CLIENT_EMPLOYEE'])
    forbidden = client.get('/ai/review/conversations')
    assert forbidden.status_code == 403

    app.dependency_overrides.clear()


def test_ai_review_approve_then_send_gating() -> None:
    container = DummyContainer()
    app.dependency_overrides[get_container] = lambda: container
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    send_before = client.post('/ai/review/d-1/send')
    assert send_before.status_code == 400
    assert 'approved' in send_before.json()['detail']

    approved = client.post('/ai/review/d-1/approve')
    assert approved.status_code == 200
    assert approved.json()['status'] == 'approved'

    sent = client.post('/ai/review/d-1/send')
    assert sent.status_code == 200
    assert sent.json()['status'] == 'sent'
    assert sent.json()['send_result']['status'] == 'prepared'

    history = client.get('/ai/review/history')
    assert history.status_code == 200
    assert history.json()['items'][0]['status'] == 'sent'

    app.dependency_overrides.clear()
