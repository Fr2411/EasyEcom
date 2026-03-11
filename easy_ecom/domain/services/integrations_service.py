from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from easy_ecom.core.time_utils import now_iso
from easy_ecom.domain.services.ai_context_service import InquiryPayload
from easy_ecom.data.store.postgres_models import (
    ChannelConversationModel,
    ChannelIntegrationModel,
    ChannelMessageModel,
    ClientModel,
)

ALLOWED_PROVIDERS = {"whatsapp", "messenger", "webhook"}
ALLOWED_STATUSES = {"inactive", "active", "disabled"}


@dataclass(frozen=True)
class ChannelIntegrationCreate:
    provider: str
    display_name: str
    external_account_id: str = ""
    status: str = "inactive"
    verify_token: str = ""
    inbound_secret: str = ""
    config: dict[str, str] | None = None


@dataclass(frozen=True)
class ChannelIntegrationPatch:
    display_name: str | None = None
    external_account_id: str | None = None
    status: str | None = None
    verify_token: str | None = None
    inbound_secret: str | None = None
    config: dict[str, str] | None = None


@dataclass(frozen=True)
class InboundEventPayload:
    provider_event_id: str = ""
    sender_external_id: str = ""
    sender_name: str | None = None
    message_text: str | None = None
    occurred_at: str | None = None
    metadata: dict[str, str] | None = None


@dataclass(frozen=True)
class OutboundPreparePayload:
    channel_id: str
    conversation_id: str
    message_text: str
    recipient_external_id: str
    metadata: dict[str, str] | None


class IntegrationsService:
    def __init__(self, session_factory: sessionmaker[Session], ai_context_service: object | None = None):
        self.session_factory = session_factory
        self.ai_context_service = ai_context_service

    def _integration_to_dict(self, row: ChannelIntegrationModel) -> dict[str, object]:
        return {
            "channel_id": row.channel_id,
            "provider": row.provider,
            "display_name": row.display_name,
            "status": row.status,
            "external_account_id": row.external_account_id,
            "verify_token_set": bool(row.verify_token),
            "inbound_secret_set": bool(row.inbound_secret),
            "config": self._json_to_dict(row.config_json),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "last_inbound_at": row.last_inbound_at or None,
        }

    @staticmethod
    def _json_to_dict(raw: str) -> dict[str, str]:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _trimmed(value: str | None, *, max_len: int = 255) -> str:
        return (value or "").strip()[:max_len]

    def list_integrations(self, *, client_id: str) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(ChannelIntegrationModel)
                .where(ChannelIntegrationModel.client_id == client_id)
                .order_by(ChannelIntegrationModel.created_at.desc())
            ).scalars().all()
        return [self._integration_to_dict(row) for row in rows]

    def create_integration(self, *, client_id: str, created_by_user_id: str, payload: ChannelIntegrationCreate) -> dict[str, object]:
        provider = payload.provider.strip().lower()
        if provider not in ALLOWED_PROVIDERS:
            raise ValueError("Unsupported provider")
        status = payload.status.strip().lower()
        if status not in ALLOWED_STATUSES:
            raise ValueError("Unsupported status")

        compact_config = payload.config or {}
        if len(compact_config) > 20:
            raise ValueError("config entries exceed maximum")

        created = ChannelIntegrationModel(
            channel_id=f"chl-{hashlib.sha1(f'{client_id}-{now_iso()}'.encode()).hexdigest()[:12]}",
            client_id=client_id,
            provider=provider,
            display_name=self._trimmed(payload.display_name, max_len=255),
            status=status,
            external_account_id=self._trimmed(payload.external_account_id, max_len=255),
            verify_token=self._trimmed(payload.verify_token, max_len=255),
            inbound_secret=self._trimmed(payload.inbound_secret, max_len=255),
            config_json=json.dumps(compact_config),
            created_at=now_iso(),
            updated_at=now_iso(),
            created_by_user_id=created_by_user_id,
            last_inbound_at="",
        )

        with self.session_factory() as session:
            client = session.execute(select(ClientModel.client_id).where(ClientModel.client_id == client_id)).scalar_one_or_none()
            if client is None:
                raise ValueError("Tenant not found")
            session.add(created)
            session.commit()

        return self._integration_to_dict(created)

    def patch_integration(self, *, client_id: str, channel_id: str, payload: ChannelIntegrationPatch) -> dict[str, object] | None:
        with self.session_factory() as session:
            row = session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.client_id == client_id,
                    ChannelIntegrationModel.channel_id == channel_id,
                )
            ).scalar_one_or_none()
            if row is None:
                return None

            if payload.display_name is not None:
                row.display_name = self._trimmed(payload.display_name)
            if payload.external_account_id is not None:
                row.external_account_id = self._trimmed(payload.external_account_id)
            if payload.status is not None:
                next_status = payload.status.strip().lower()
                if next_status not in ALLOWED_STATUSES:
                    raise ValueError("Unsupported status")
                row.status = next_status
            if payload.verify_token is not None:
                row.verify_token = self._trimmed(payload.verify_token)
            if payload.inbound_secret is not None:
                row.inbound_secret = self._trimmed(payload.inbound_secret)
            if payload.config is not None:
                if len(payload.config) > 20:
                    raise ValueError("config entries exceed maximum")
                row.config_json = json.dumps(payload.config)
            row.updated_at = now_iso()
            session.commit()
            session.refresh(row)
        return self._integration_to_dict(row)

    def list_messages(self, *, client_id: str, limit: int = 50) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(ChannelMessageModel)
                .where(ChannelMessageModel.client_id == client_id)
                .order_by(ChannelMessageModel.occurred_at.desc())
                .limit(max(1, min(limit, 100)))
            ).scalars().all()
        return [
            {
                "message_id": row.message_id,
                "conversation_id": row.conversation_id,
                "channel_id": row.channel_id,
                "direction": row.direction,
                "external_sender_id": row.external_sender_id,
                "provider_event_id": row.provider_event_id,
                "message_text": row.message_text,
                "content_summary": row.content_summary,
                "occurred_at": row.occurred_at,
                "outbound_status": row.outbound_status,
            }
            for row in rows
        ]

    @staticmethod
    def verify_inbound_signature(*, request_body: bytes, signature: str, timestamp: str, secret: str) -> bool:
        if not secret or not signature or not timestamp:
            return False
        signed_payload = f"{timestamp}.".encode() + request_body
        expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def is_recent_timestamp(timestamp: str, tolerance_seconds: int = 300) -> bool:
        try:
            ts = int(timestamp)
        except ValueError:
            return False
        now_ts = int(datetime.now(UTC).timestamp())
        return abs(now_ts - ts) <= tolerance_seconds


    def get_active_channel_for_verification(self, *, provider: str, channel_id: str) -> ChannelIntegrationModel | None:
        with self.session_factory() as session:
            return session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.channel_id == channel_id,
                    ChannelIntegrationModel.provider == provider.strip().lower(),
                    ChannelIntegrationModel.status == "active",
                )
            ).scalar_one_or_none()

    def ingest_inbound_event(
        self,
        *,
        provider: str,
        channel_id: str,
        payload: InboundEventPayload,
    ) -> dict[str, object]:
        provider_name = provider.strip().lower()
        if provider_name not in ALLOWED_PROVIDERS:
            raise ValueError("Unsupported provider")
        sender_external_id = payload.sender_external_id.strip()
        if not sender_external_id:
            raise ValueError("sender_external_id is required")

        occurred_at = payload.occurred_at or now_iso()
        message_text = (payload.message_text or "").strip()

        with self.session_factory() as session:
            integration = session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.channel_id == channel_id,
                    ChannelIntegrationModel.provider == provider_name,
                    ChannelIntegrationModel.status == "active",
                )
            ).scalar_one_or_none()
            if integration is None:
                raise ValueError("Active channel integration not found")

            conversation = session.execute(
                select(ChannelConversationModel).where(
                    ChannelConversationModel.client_id == integration.client_id,
                    ChannelConversationModel.channel_id == integration.channel_id,
                    ChannelConversationModel.external_sender_id == sender_external_id,
                )
            ).scalar_one_or_none()
            if conversation is None:
                conversation = ChannelConversationModel(
                    conversation_id=f"conv-{hashlib.sha1(f'{integration.client_id}-{channel_id}-{sender_external_id}'.encode()).hexdigest()[:12]}",
                    client_id=integration.client_id,
                    channel_id=integration.channel_id,
                    external_sender_id=sender_external_id,
                    status="open",
                    customer_id="",
                    linked_sale_id="",
                    created_at=now_iso(),
                    updated_at=now_iso(),
                    last_message_at=occurred_at,
                )
                session.add(conversation)
            else:
                conversation.updated_at = now_iso()
                conversation.last_message_at = occurred_at

            message = ChannelMessageModel(
                message_id=f"msg-{hashlib.sha1(f'{integration.client_id}-{payload.provider_event_id}-{now_iso()}'.encode()).hexdigest()[:12]}",
                client_id=integration.client_id,
                channel_id=integration.channel_id,
                conversation_id=conversation.conversation_id,
                direction="inbound",
                provider_event_id=(payload.provider_event_id or "").strip()[:255],
                external_sender_id=sender_external_id,
                message_text=message_text,
                content_summary=message_text[:280],
                payload_json=json.dumps(payload.metadata or {}),
                occurred_at=occurred_at,
                created_at=now_iso(),
                outbound_status="received",
                created_by_user_id="system:inbound",
            )
            integration.last_inbound_at = now_iso()
            integration.updated_at = now_iso()
            session.add(message)
            session.commit()

        return {
            "accepted": True,
            "client_id": integration.client_id,
            "channel_id": channel_id,
            "conversation_id": conversation.conversation_id,
            "message_id": message.message_id,
        }

    def list_conversations(self, *, client_id: str, limit: int = 50) -> list[dict[str, object]]:
        with self.session_factory() as session:
            rows = session.execute(
                select(ChannelConversationModel)
                .where(ChannelConversationModel.client_id == client_id)
                .order_by(ChannelConversationModel.last_message_at.desc())
                .limit(max(1, min(limit, 100)))
            ).scalars().all()
        return [
            {
                "conversation_id": row.conversation_id,
                "channel_id": row.channel_id,
                "external_sender_id": row.external_sender_id,
                "status": row.status,
                "customer_id": row.customer_id or None,
                "linked_sale_id": row.linked_sale_id or None,
                "last_message_at": row.last_message_at,
                "updated_at": row.updated_at,
            }
            for row in rows
        ]

    def get_conversation(self, *, client_id: str, conversation_id: str) -> dict[str, object] | None:
        with self.session_factory() as session:
            conversation = session.execute(
                select(ChannelConversationModel).where(
                    ChannelConversationModel.client_id == client_id,
                    ChannelConversationModel.conversation_id == conversation_id,
                )
            ).scalar_one_or_none()
            if conversation is None:
                return None

            messages = session.execute(
                select(ChannelMessageModel).where(
                    ChannelMessageModel.client_id == client_id,
                    ChannelMessageModel.conversation_id == conversation_id,
                )
            ).scalars().all()

        return {
            "conversation_id": conversation.conversation_id,
            "channel_id": conversation.channel_id,
            "external_sender_id": conversation.external_sender_id,
            "status": conversation.status,
            "messages": [
                {
                    "message_id": msg.message_id,
                    "direction": msg.direction,
                    "message_text": msg.message_text,
                    "content_summary": msg.content_summary,
                    "occurred_at": msg.occurred_at,
                    "outbound_status": msg.outbound_status,
                }
                for msg in sorted(messages, key=lambda m: m.occurred_at)
            ],
        }

    def prepare_outbound(
        self,
        *,
        client_id: str,
        created_by_user_id: str,
        payload: OutboundPreparePayload,
    ) -> dict[str, object]:
        text = payload.message_text.strip()
        if not text:
            raise ValueError("message_text is required")

        with self.session_factory() as session:
            integration = session.execute(
                select(ChannelIntegrationModel).where(
                    ChannelIntegrationModel.client_id == client_id,
                    ChannelIntegrationModel.channel_id == payload.channel_id,
                )
            ).scalar_one_or_none()
            if integration is None:
                raise ValueError("Channel not found")

            conversation = session.execute(
                select(ChannelConversationModel).where(
                    ChannelConversationModel.client_id == client_id,
                    ChannelConversationModel.conversation_id == payload.conversation_id,
                )
            ).scalar_one_or_none()
            if conversation is None:
                raise ValueError("Conversation not found")

            message = ChannelMessageModel(
                message_id=f"msg-{hashlib.sha1(f'{client_id}-{text}-{now_iso()}'.encode()).hexdigest()[:12]}",
                client_id=client_id,
                channel_id=payload.channel_id,
                conversation_id=payload.conversation_id,
                direction="outbound",
                provider_event_id="",
                external_sender_id=payload.recipient_external_id.strip()[:255],
                message_text=text,
                content_summary=text[:280],
                payload_json=json.dumps(payload.metadata or {}),
                occurred_at=now_iso(),
                created_at=now_iso(),
                outbound_status="prepared",
                created_by_user_id=created_by_user_id,
            )
            session.add(message)
            session.commit()

        ai_context_hint = None
        if self.ai_context_service is not None:
            try:
                ai_context_hint = self.ai_context_service.handle_inbound_inquiry(
                    client_id=client_id,
                    payload=InquiryPayload(message=text, customer_ref=None),
                )
            except Exception:
                ai_context_hint = None

        return {
            "dispatch_intent_id": message.message_id,
            "status": "prepared",
            "provider": integration.provider,
            "delivery_deferred": True,
            "deferred_reason": "Provider delivery adapter is intentionally deferred in Phase 14.",
            "ai_context_hint": ai_context_hint,
        }
