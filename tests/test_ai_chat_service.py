from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from easy_ecom.core.ids import new_uuid
from easy_ecom.data.store.postgres_db import Base
from easy_ecom.data.store.postgres_models import (
    AIAgentProfileModel,
    AIChatChannelModel,
    AIConversationModel,
    AIMessageModel,
    ClientModel,
)
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.domain.services.ai_chat_service import AIChatService


class AIChatServiceTests(unittest.TestCase):
    def test_build_ai_model_messages_replays_recent_turns(self) -> None:
        service = AIChatService(sessionmaker())

        context_payload = {
            "business": {
                "business_name": "Tenant Store",
                "currency_code": "USD",
                "currency_symbol": "$",
                "timezone": "UTC",
                "website_url": "https://tenant.example",
                "phone": "+1 555 0100",
                "email": "hello@tenant.example",
                "address": "Main Street",
            },
            "agent": {
                "display_name": "Lina",
                "persona_prompt": "Warm, concise, and helpful.",
                "store_policy": "Only promise items that are in stock.",
                "faq_entries": [{"question": "Delivery", "answer": "2 days"}],
                "escalation_rules": ["Send damaged-item cases to a human"],
                "allowed_actions": {
                    "product_qa": True,
                    "recommendations": True,
                    "cart_building": True,
                    "order_confirmation": True,
                },
                "opening_message": "Hi! I can help you find the right item.",
                "handoff_message": "Our team will take over from here.",
            },
            "customer": {
                "name": "Rima",
                "phone": "",
                "email": "",
                "address": "",
            },
            "conversation": {
                "conversation_id": str(uuid4()),
                "status": "open",
                "latest_intent": "availability",
                "latest_summary": "Customer asked about a black travel bag.",
                "recent_messages": [
                    {"direction": "inbound", "text": "Hi there"},
                    {"direction": "outbound", "text": "Hello! What can I help you with today?"},
                    {"direction": "inbound", "text": "Do you have a black travel bag?"},
                ],
            },
            "stock_location": {
                "location_id": str(uuid4()),
                "location_name": "Main Warehouse",
            },
            "catalog": {
                "items": [
                    {
                        "variant_id": str(uuid4()),
                        "product_id": str(uuid4()),
                        "product_name": "Travel Bag",
                        "variant_title": "Black",
                        "label": "Travel Bag / Black",
                        "sku": "TB-BLK",
                        "brand": "EasyEcom",
                        "category": "Bags",
                        "supplier": "Prime Supplier",
                        "description": "Lightweight carry-on bag",
                        "unit_price": "120.00",
                        "min_price": "110.00",
                        "on_hand": "8",
                        "reserved": "1",
                        "available_to_sell": "7",
                        "can_sell": True,
                    }
                ],
                "source": "EasyEcom stock",
            },
            "current_customer_message": "Do you have a black travel bag?",
            "guardrails": [
                "Use only EasyEcom facts.",
                "Ask one clear follow-up question at a time.",
            ],
        }

        messages = service._build_ai_model_messages(context_payload)

        self.assertGreater(len(messages), 3)
        self.assertEqual(messages[-1]["role"], "user")
        self.assertEqual(messages[-1]["content"], "Do you have a black travel bag?")
        self.assertTrue(any(message["role"] == "assistant" and "Hello!" in message["content"] for message in messages))

    def test_parse_ai_model_response_extracts_embedded_json(self) -> None:
        service = AIChatService(sessionmaker())

        payload = service._parse_ai_model_response(
            'Here is the answer you requested:\n{"reply_text":"Yes, it is available.","handoff_required":false,"handoff_reason":"","latest_intent":"availability","latest_summary":"Confirmed stock for black travel bag.","action":{"type":"none"}}\nThanks.'
        )

        self.assertEqual(payload["reply_text"], "Yes, it is available.")
        self.assertFalse(payload["handoff_required"])
        self.assertEqual(payload["latest_intent"], "availability")

    def test_parse_ai_model_response_fails_closed_for_invalid_output(self) -> None:
        service = AIChatService(sessionmaker())

        payload = service._parse_ai_model_response("Sure, I can help with that right now.")

        self.assertTrue(payload["handoff_required"])
        self.assertEqual(payload["latest_intent"], "handoff")
        self.assertEqual(payload["action"], {"type": "none"})

    def test_record_public_inbound_keeps_existing_handoff_conversation_in_handoff(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "test-widget-key"
        browser_session_id = "browser-session-123"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key=widget_key,
                    allowed_origins_json=[],
                )
            )
            session.add(
                AIConversationModel(
                    ai_conversation_id=conversation_id,
                    client_id=client_id,
                    ai_chat_channel_id=channel_id,
                    browser_session_id=browser_session_id,
                    status="handoff",
                    handoff_reason="Customer asked for a manager",
                    customer_name_snapshot="Rima",
                )
            )
            session.commit()

        payload = service._record_public_inbound(
            widget_key=widget_key,
            browser_session_id=browser_session_id,
            client_message_id="handoff-msg-001",
            message="Are you there?",
            customer=None,
            metadata={"source": "unit_test"},
            origin="",
            client_ip="127.0.0.1",
            trusted_origins=None,
        )

        self.assertTrue(payload["handoff_required"])
        self.assertEqual(payload["handoff_reason"], "Customer asked for a manager")

    def test_get_conversation_detail_returns_recent_transcript(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-2",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key="detail-widget-key",
                    allowed_origins_json=[],
                )
            )
            session.add(
                AIConversationModel(
                    ai_conversation_id=conversation_id,
                    client_id=client_id,
                    ai_chat_channel_id=channel_id,
                    browser_session_id="browser-session-456",
                    status="open",
                    customer_name_snapshot="Rima",
                    customer_phone_snapshot="+8801000",
                    latest_intent="availability",
                    latest_summary="Customer asked about travel bag availability",
                    last_message_preview="Yes, the black travel bag is available.",
                )
            )
            session.add_all(
                [
                    AIMessageModel(
                        ai_message_id=new_uuid(),
                        client_id=client_id,
                        ai_conversation_id=conversation_id,
                        ai_chat_channel_id=channel_id,
                        direction="inbound",
                        message_text="Do you have the black travel bag?",
                        content_summary="Do you have the black travel bag?",
                    ),
                    AIMessageModel(
                        ai_message_id=new_uuid(),
                        client_id=client_id,
                        ai_conversation_id=conversation_id,
                        ai_chat_channel_id=channel_id,
                        direction="outbound",
                        message_text="Yes, it is available.",
                        content_summary="Yes, it is available.",
                        model_name="gpt-4o-mini",
                    ),
                ]
            )
            session.commit()

        user = AuthenticatedUser(
            user_id=str(uuid4()),
            client_id=client_id,
            name="Owner",
            email="owner@tenant.example",
            business_name="Tenant Store",
            roles=["CLIENT_OWNER"],
            allowed_pages=["AI Assistant", "Settings"],
            billing_plan_code="scale",
            billing_status="active",
            billing_access_state="paid_active",
        )

        detail = service.get_conversation_detail(user, conversation_id=conversation_id, message_limit=20)

        self.assertEqual(detail["conversation_id"], conversation_id)
        self.assertEqual(detail["customer_name"], "Rima")
        self.assertEqual(len(detail["messages"]), 2)
        self.assertEqual(detail["messages"][0]["direction"], "inbound")
        self.assertEqual(detail["messages"][1]["direction"], "outbound")
        self.assertIn("available", detail["messages"][1]["text"])

    def test_handle_public_message_reuses_existing_response_for_duplicate_client_message_id(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        widget_key = "dedupe-widget-key"
        browser_session_id = "browser-session-dedupe"
        client_message_id = "msg-001"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-3",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key=widget_key,
                    allowed_origins_json=[],
                )
            )
            session.commit()

        ai_reply = {
            "reply_text": "Yes, the black travel bag is available.",
            "handoff_required": False,
            "handoff_reason": "",
            "order_status": None,
            "latest_intent": "availability",
            "latest_summary": "Confirmed black travel bag stock.",
            "ai_metadata": {"ai_runtime": "easy_ecom"},
        }

        with patch.object(service, "_invoke_easy_ecom_ai", return_value=ai_reply) as invoke_mock:
            first = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id=browser_session_id,
                client_message_id=client_message_id,
                message="Do you have the black travel bag?",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )
            second = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id=browser_session_id,
                client_message_id=client_message_id,
                message="Do you have the black travel bag?",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        self.assertEqual(invoke_mock.call_count, 1)
        self.assertEqual(first["reply_text"], second["reply_text"])
        self.assertEqual(first["outbound_message_id"], second["outbound_message_id"])

    def test_handle_public_message_recovers_from_duplicate_insert_race(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        widget_key = "race-widget-key"
        browser_session_id = "browser-session-race"
        client_message_id = "msg-race-001"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-race",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key=widget_key,
                    allowed_origins_json=[],
                )
            )
            session.commit()

        ai_reply = {
            "reply_text": "Yes, the black travel bag is available.",
            "handoff_required": False,
            "handoff_reason": "",
            "order_status": None,
            "latest_intent": "availability",
            "latest_summary": "Confirmed black travel bag stock.",
            "ai_metadata": {"ai_runtime": "easy_ecom"},
        }

        with patch.object(service, "_invoke_easy_ecom_ai", return_value=ai_reply):
            first = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id=browser_session_id,
                client_message_id=client_message_id,
                message="Do you have the black travel bag?",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        existing_payload = dict(first)
        existing_payload["was_duplicate"] = True

        with patch.object(service, "_duplicate_public_message_response", side_effect=[None, existing_payload]):
            second = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id=browser_session_id,
                client_message_id=client_message_id,
                message="Do you have the black travel bag?",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        self.assertTrue(second["was_duplicate"])
        self.assertEqual(first["outbound_message_id"], second["outbound_message_id"])

    def test_update_conversation_status_can_reopen_and_clear_handoff_reason(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-4",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key="status-widget-key",
                    allowed_origins_json=[],
                )
            )
            session.add(
                AIConversationModel(
                    ai_conversation_id=conversation_id,
                    client_id=client_id,
                    ai_chat_channel_id=channel_id,
                    browser_session_id="browser-session-789",
                    status="handoff",
                    handoff_reason="Customer asked for a manager",
                    latest_summary="Escalated to team",
                )
            )
            session.commit()

        user = AuthenticatedUser(
            user_id=str(uuid4()),
            client_id=client_id,
            name="Owner",
            email="owner@tenant.example",
            business_name="Tenant Store",
            roles=["CLIENT_OWNER"],
            allowed_pages=["AI Assistant", "Settings"],
            billing_plan_code="scale",
            billing_status="active",
            billing_access_state="paid_active",
        )

        updated = service.update_conversation_status(
            user,
            conversation_id=conversation_id,
            status="open",
            handoff_reason="",
        )

        self.assertEqual(updated["status"], "open")
        self.assertEqual(updated["handoff_reason"], "")

    def test_closed_conversation_does_not_auto_reply_with_ai(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "closed-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-closed",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key=widget_key,
                    allowed_origins_json=[],
                )
            )
            session.add(
                AIConversationModel(
                    ai_conversation_id=conversation_id,
                    client_id=client_id,
                    ai_chat_channel_id=channel_id,
                    browser_session_id="browser-session-closed",
                    status="closed",
                    handoff_reason="Handled by the team",
                )
            )
            session.commit()

        with patch.object(service, "_invoke_easy_ecom_ai") as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-closed",
                client_message_id="msg-closed-001",
                message="I still need help",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_not_called()
        self.assertEqual(result["status"], "closed")
        self.assertTrue(result["handoff_required"])

    def test_handoff_status_blocks_ai_even_without_existing_handoff_reason(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "handoff-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-handoff",
                    business_name="Tenant Store",
                    contact_name="Owner",
                    owner_name="Owner",
                    phone="+1 555 0100",
                    email="owner@tenant.example",
                    address="Main Street",
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    website_url="https://tenant.example",
                    facebook_url="",
                    instagram_url="",
                    whatsapp_number="",
                    status="active",
                    notes="",
                    billing_plan_code="scale",
                    billing_status="active",
                    billing_access_state="paid_active",
                )
            )
            session.add(
                AIAgentProfileModel(
                    ai_agent_profile_id=profile_id,
                    client_id=client_id,
                    is_enabled=True,
                    display_name="Lina",
                    persona_prompt="Warm and concise",
                    store_policy="Never promise unavailable stock",
                    faq_json=[],
                    escalation_rules_json=[],
                    allowed_actions_json={},
                    opening_message="Hello!",
                    handoff_message="A human teammate will continue from here.",
                )
            )
            session.add(
                AIChatChannelModel(
                    ai_chat_channel_id=channel_id,
                    client_id=client_id,
                    agent_profile_id=profile_id,
                    channel_type="website",
                    display_name="Lina",
                    status="active",
                    widget_key=widget_key,
                    allowed_origins_json=[],
                )
            )
            session.add(
                AIConversationModel(
                    ai_conversation_id=conversation_id,
                    client_id=client_id,
                    ai_chat_channel_id=channel_id,
                    browser_session_id="browser-session-handoff",
                    status="handoff",
                    handoff_reason="",
                )
            )
            session.commit()

        with patch.object(service, "_invoke_easy_ecom_ai") as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-handoff",
                client_message_id="msg-handoff-001",
                message="Checking in again",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_not_called()
        self.assertEqual(result["status"], "handoff")
        self.assertTrue(result["handoff_required"])


if __name__ == "__main__":
    unittest.main()
