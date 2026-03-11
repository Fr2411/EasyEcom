from __future__ import annotations

import hashlib
import hmac
import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from easy_ecom.api.dependencies import RequestUser, get_container, get_current_user
from easy_ecom.api.main import app, create_app


class DummyIntegrationsService:
    def __init__(self) -> None:
        self.channels = {
            "tenant-a": [{"channel_id": "chl-a1", "provider": "webhook", "display_name": "A", "status": "active", "external_account_id": "", "verify_token_set": True, "inbound_secret_set": True, "config": {}, "created_at": "", "updated_at": "", "last_inbound_at": None}],
            "tenant-b": [],
        }
        self.messages = {"tenant-a": [], "tenant-b": []}
        self.conversations = {"tenant-a": [{"conversation_id": "conv-1", "channel_id": "chl-a1", "external_sender_id": "wa_1", "status": "open", "customer_id": None, "linked_sale_id": None, "last_message_at": "", "updated_at": ""}], "tenant-b": []}
        self.secret = "secret123"

    def list_integrations(self, *, client_id: str):
        return self.channels.get(client_id, [])

    def create_integration(self, *, client_id: str, created_by_user_id: str, payload):
        item = {"channel_id": "chl-new", "provider": payload.provider, "display_name": payload.display_name, "status": payload.status, "external_account_id": payload.external_account_id, "verify_token_set": bool(payload.verify_token), "inbound_secret_set": bool(payload.inbound_secret), "config": payload.config or {}, "created_at": "", "updated_at": "", "last_inbound_at": None}
        self.channels.setdefault(client_id, []).append(item)
        return item

    def patch_integration(self, *, client_id: str, channel_id: str, payload):
        for item in self.channels.get(client_id, []):
            if item["channel_id"] == channel_id:
                if payload.status:
                    item["status"] = payload.status
                return item
        return None

    def list_messages(self, *, client_id: str, limit: int = 50):
        return self.messages.get(client_id, [])[:limit]

    def is_recent_timestamp(self, timestamp: str, tolerance_seconds: int = 300):
        return True

    def verify_inbound_signature(self, *, request_body: bytes, signature: str, timestamp: str, secret: str):
        expected = hmac.new(secret.encode(), f"{timestamp}.".encode() + request_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @property
    def session_factory(self):
        class Dummy:
            def __enter__(self_inner):
                class Session:
                    def execute(self, *_args, **_kwargs):
                        class R:
                            def scalar_one_or_none(_self):
                                class I:
                                    inbound_secret = "secret123"
                                return I()
                        return R()

                return Session()

            def __exit__(self_inner, *args):
                return False

        return Dummy


    def get_active_channel_for_verification(self, *, provider: str, channel_id: str):
        if provider == "webhook" and channel_id == "chl-a1":
            class I:
                inbound_secret = "secret123"
            return I()
        return None

    def ingest_inbound_event(self, *, provider: str, channel_id: str, payload):
        return {"accepted": True, "client_id": "tenant-a", "channel_id": channel_id, "conversation_id": "conv-1", "message_id": "msg-1"}

    def prepare_outbound(self, *, client_id: str, created_by_user_id: str, payload):
        return {"dispatch_intent_id": "msg-out", "status": "prepared", "provider": "webhook", "delivery_deferred": True, "deferred_reason": "Deferred", "ai_context_hint": {"intent": "stock_check"}}

    def list_conversations(self, *, client_id: str, limit: int = 50):
        return self.conversations.get(client_id, [])[:limit]

    def get_conversation(self, *, client_id: str, conversation_id: str):
        if client_id == "tenant-a" and conversation_id == "conv-1":
            return {"conversation_id": "conv-1", "channel_id": "chl-a1", "external_sender_id": "wa_1", "status": "open", "messages": []}
        return None


class DummyContainer:
    def __init__(self) -> None:
        self.integrations = DummyIntegrationsService()


def test_integrations_requires_authentication() -> None:
    client = TestClient(create_app())
    resp = client.get('/integrations/channels')
    assert resp.status_code == 401


def test_integrations_access_control_and_tenant_isolation() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    channels = client.get('/integrations/channels')
    assert channels.status_code == 200
    assert len(channels.json()['items']) == 1

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u2', client_id='tenant-b', roles=['CLIENT_OWNER'])
    channels_b = client.get('/integrations/channels')
    assert channels_b.status_code == 200
    assert channels_b.json()['items'] == []

    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u3', client_id='tenant-a', roles=['CLIENT_EMPLOYEE'])
    forbidden = client.get('/integrations/channels')
    assert forbidden.status_code == 403

    app.dependency_overrides.clear()


def test_inbound_verification_and_outbound_prepare() -> None:
    app.dependency_overrides[get_container] = lambda: DummyContainer()
    app.dependency_overrides[get_current_user] = lambda: RequestUser(user_id='u1', client_id='tenant-a', roles=['CLIENT_OWNER'])
    client = TestClient(app)

    body = {"provider_event_id": "evt-1", "sender_external_id": "wa-123", "message_text": "Need stock"}
    body_bytes = json.dumps(body).encode()
    timestamp = str(int(datetime.now(UTC).timestamp()))
    signature = hmac.new(b'secret123', f'{timestamp}.'.encode() + body_bytes, hashlib.sha256).hexdigest()

    bad_sig = client.post('/integrations/inbound/webhook', json=body, headers={"x-channel-id": "chl-a1", "x-channel-timestamp": timestamp, "x-channel-signature": "bad"})
    assert bad_sig.status_code == 401

    ok = client.post('/integrations/inbound/webhook', content=body_bytes, headers={"content-type": "application/json", "x-channel-id": "chl-a1", "x-channel-timestamp": timestamp, "x-channel-signature": signature})
    assert ok.status_code == 200
    assert ok.json()['accepted'] is True

    prepared = client.post('/integrations/outbound/prepare', json={"channel_id": "chl-a1", "conversation_id": "conv-1", "message_text": "We have it", "recipient_external_id": "wa-123"})
    assert prepared.status_code == 200
    assert prepared.json()['delivery_deferred'] is True
    assert prepared.json()['ai_context_hint']['intent'] == 'stock_check'

    app.dependency_overrides.clear()
