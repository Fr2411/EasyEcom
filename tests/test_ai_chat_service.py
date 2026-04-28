from __future__ import annotations

from decimal import Decimal
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
    ProductModel,
    ProductVariantModel,
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

    def test_extract_shopping_preferences_uses_recent_turns_for_follow_up_budget_request(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="I need something cheaper under AED 200, still good for gym use. What do you recommend?",
            recent_context=[
                {"direction": "inbound", "text": "Do you have a black running shoe in EU 42 for daily running?"},
                {"direction": "outbound", "text": "Yes, the AeroRun shoe is available for AED 289."},
            ],
            existing_preferences={},
        )

        self.assertEqual(preferences["max_budget"], "200")
        self.assertEqual(preferences["price_preference"], "lower")
        self.assertIn("black", preferences["colors"])
        self.assertIn("42", preferences["sizes"])
        self.assertTrue(any("running" in term for term in preferences["product_terms"]))
        self.assertIn("gym", preferences["use_case_terms"])
        self.assertTrue(preferences["wants_recommendation"])

    def test_deterministic_catalog_reply_recommends_budget_matching_options(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "inbound", "text": "Do you have a black running shoe in EU 42 for daily running?"},
                        {"direction": "outbound", "text": "Yes, the AeroRun Flex Knit Running Shoe is AED 289.00."},
                    ],
                    "shopping_preferences": {},
                },
                "current_customer_message": "I need something cheaper under AED 200, still good for gym use. What do you recommend?",
                "catalog": {
                    "items": [
                        {
                            "label": "AeroRun Flex Knit Running Shoe / Black / EU 42",
                            "product_name": "AeroRun Flex Knit Running Shoe",
                            "variant_title": "Black / EU 42",
                            "description": "Breathable daily running shoe for gym sessions",
                            "unit_price": Decimal("289.00"),
                            "available_to_sell": Decimal("4"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "MotionCore Runner / Black / EU 42",
                            "product_name": "MotionCore Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Comfortable running shoe for gym and treadmill use",
                            "unit_price": Decimal("195.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertFalse(reply["handoff_required"])
        self.assertEqual(reply["latest_intent"], "recommendation")
        self.assertIn("SprintLite Trainer", reply["reply_text"])
        self.assertIn("MotionCore Runner", reply["reply_text"])
        self.assertNotIn("AeroRun Flex Knit Running Shoe", reply["reply_text"])

    def test_deterministic_catalog_reply_budget_only_follow_up_uses_saved_product_context(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"},
                        {"direction": "outbound", "text": "Yes, the AeroRun shoe is available for AED 289.00."},
                    ],
                    "shopping_preferences": {"product_terms": ["running", "shoe"], "colors": ["black"], "sizes": ["42"]},
                },
                "current_customer_message": "Actually something under AED 200 instead.",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "MotionCore Runner / Black / EU 42",
                            "product_name": "MotionCore Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Comfortable running shoe for gym and treadmill use",
                            "unit_price": Decimal("195.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertNotIn("do not currently see", reply["reply_text"].lower())
        self.assertIn("SprintLite Trainer", reply["reply_text"])

    def test_deterministic_catalog_reply_handles_budget_discovery_request(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "Show me a budget option for running shoes.",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "AeroRun Elite / Black / EU 42",
                            "product_name": "AeroRun Elite",
                            "variant_title": "Black / EU 42",
                            "description": "Premium running shoe",
                            "unit_price": Decimal("289.00"),
                            "available_to_sell": Decimal("4"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertEqual(reply["latest_intent"], "recommendation")
        self.assertIn("SprintLite Trainer", reply["reply_text"])
        self.assertNotIn("do not currently see", reply["reply_text"].lower())

    def test_invoke_easy_ecom_ai_uses_deterministic_catalog_reply_when_model_request_fails(self) -> None:
        service = AIChatService(sessionmaker())
        context_payload = {
            "business": {"currency_code": "AED", "currency_symbol": "AED"},
            "agent": {"handoff_message": "Our team will help from here."},
            "conversation": {
                "recent_messages": [
                    {"direction": "inbound", "text": "Do you have a black running shoe in EU 42 for daily running?"},
                    {"direction": "outbound", "text": "Yes, the AeroRun Flex Knit Running Shoe is AED 289.00."},
                ],
                "shopping_preferences": {},
            },
            "current_customer_message": "I need something cheaper under AED 200, still good for gym use. What do you recommend?",
            "catalog": {
                "items": [
                    {
                        "label": "SprintLite Trainer / Black / EU 42",
                        "product_name": "SprintLite Trainer",
                        "variant_title": "Black / EU 42",
                        "description": "Affordable gym trainer for daily workouts",
                        "unit_price": Decimal("189.00"),
                        "available_to_sell": Decimal("6"),
                        "can_sell": True,
                        "category": "Running Shoes",
                        "brand": "Frabby",
                    }
                ]
            },
        }

        with (
            patch.object(service, "_build_ai_context", return_value=context_payload),
            patch.object(service, "_call_ai_model", side_effect=RuntimeError("model boom")),
            patch.object(service, "_audit_ai_model_step") as audit_mock,
        ):
            payload = service._invoke_easy_ecom_ai(
                client_id=str(uuid4()),
                conversation_id=str(uuid4()),
                inbound_message_id=str(uuid4()),
                text=context_payload["current_customer_message"],
                recent_context=context_payload["conversation"]["recent_messages"],
                fallback_message="A human teammate will continue from here.",
            )

        self.assertFalse(payload["handoff_required"])
        self.assertIn("SprintLite Trainer", payload["reply_text"])
        self.assertEqual(payload["latest_intent"], "recommendation")
        audit_mock.assert_called()

    def test_invoke_easy_ecom_ai_handles_simple_greeting_without_handoff_when_model_would_fail(self) -> None:
        service = AIChatService(sessionmaker())
        context_payload = {
            "business": {"currency_code": "AED", "currency_symbol": "AED"},
            "agent": {
                "display_name": "Frabby Footwear Assistant",
                "handoff_message": "Our team will help from here.",
            },
            "conversation": {"recent_messages": [], "shopping_preferences": {}},
            "current_customer_message": "Hi",
            "catalog": {"items": []},
        }

        with (
            patch.object(service, "_build_ai_context", return_value=context_payload),
            patch.object(service, "_call_ai_model") as call_model_mock,
            patch.object(service, "_audit_ai_model_step") as audit_mock,
        ):
            payload = service._invoke_easy_ecom_ai(
                client_id=str(uuid4()),
                conversation_id=str(uuid4()),
                inbound_message_id=str(uuid4()),
                text="Hi",
                recent_context=[],
                fallback_message="A human teammate will continue from here.",
            )

        self.assertFalse(payload["handoff_required"])
        self.assertEqual(payload["latest_intent"], "other")
        self.assertIn("help", payload["reply_text"].lower())
        call_model_mock.assert_not_called()
        audit_mock.assert_called()

    def test_invoke_easy_ecom_ai_handles_multiword_greeting_without_handoff_when_model_would_fail(self) -> None:
        service = AIChatService(sessionmaker())
        context_payload = {
            "business": {"currency_code": "AED", "currency_symbol": "AED"},
            "agent": {
                "display_name": "Frabby Footwear Assistant",
                "handoff_message": "Our team will help from here.",
            },
            "conversation": {"recent_messages": [], "shopping_preferences": {}},
            "current_customer_message": "Good morning",
            "catalog": {"items": []},
        }

        with (
            patch.object(service, "_build_ai_context", return_value=context_payload),
            patch.object(service, "_call_ai_model") as call_model_mock,
            patch.object(service, "_audit_ai_model_step") as audit_mock,
        ):
            payload = service._invoke_easy_ecom_ai(
                client_id=str(uuid4()),
                conversation_id=str(uuid4()),
                inbound_message_id=str(uuid4()),
                text="Good morning",
                recent_context=[],
                fallback_message="A human teammate will continue from here.",
            )

        self.assertFalse(payload["handoff_required"])
        self.assertEqual(payload["latest_intent"], "other")
        self.assertIn("help", payload["reply_text"].lower())
        call_model_mock.assert_not_called()
        audit_mock.assert_called()

    def test_invoke_easy_ecom_ai_handles_i_did_not_ask_yet_without_handoff(self) -> None:
        service = AIChatService(sessionmaker())
        context_payload = {
            "business": {"currency_code": "AED", "currency_symbol": "AED"},
            "agent": {
                "display_name": "Frabby Footwear Assistant",
                "handoff_message": "Our team will help from here.",
            },
            "conversation": {
                "recent_messages": [
                    {"direction": "outbound", "text": "Thanks for the details. I am sending this to the Frabby Footwear team so they can check it properly and help you."}
                ],
                "shopping_preferences": {},
            },
            "current_customer_message": "I didn't ask for anything yet.",
            "catalog": {"items": []},
        }

        with (
            patch.object(service, "_build_ai_context", return_value=context_payload),
            patch.object(service, "_call_ai_model") as call_model_mock,
            patch.object(service, "_audit_ai_model_step") as audit_mock,
        ):
            payload = service._invoke_easy_ecom_ai(
                client_id=str(uuid4()),
                conversation_id=str(uuid4()),
                inbound_message_id=str(uuid4()),
                text="I didn't ask for anything yet.",
                recent_context=context_payload["conversation"]["recent_messages"],
                fallback_message="A human teammate will continue from here.",
            )

        self.assertFalse(payload["handoff_required"])
        self.assertEqual(payload["latest_intent"], "other")
        self.assertIn("sorry", payload["reply_text"].lower())
        self.assertIn("looking for", payload["reply_text"].lower())
        call_model_mock.assert_not_called()
        audit_mock.assert_called()

    def test_invoke_easy_ecom_ai_handles_curly_apostrophe_reset_without_handoff(self) -> None:
        service = AIChatService(sessionmaker())
        context_payload = {
            "business": {"currency_code": "AED", "currency_symbol": "AED"},
            "agent": {
                "display_name": "Frabby Footwear Assistant",
                "handoff_message": "Our team will help from here.",
            },
            "conversation": {
                "recent_messages": [
                    {"direction": "outbound", "text": "Thanks for the details. I am sending this to the Frabby Footwear team so they can check it properly and help you."}
                ],
                "shopping_preferences": {},
            },
            "current_customer_message": "I didn’t ask for anything yet.",
            "catalog": {"items": []},
        }

        with (
            patch.object(service, "_build_ai_context", return_value=context_payload),
            patch.object(service, "_call_ai_model") as call_model_mock,
            patch.object(service, "_audit_ai_model_step") as audit_mock,
        ):
            payload = service._invoke_easy_ecom_ai(
                client_id=str(uuid4()),
                conversation_id=str(uuid4()),
                inbound_message_id=str(uuid4()),
                text="I didn’t ask for anything yet.",
                recent_context=context_payload["conversation"]["recent_messages"],
                fallback_message="A human teammate will continue from here.",
            )

        self.assertFalse(payload["handoff_required"])
        self.assertEqual(payload["latest_intent"], "other")
        self.assertIn("sorry", payload["reply_text"].lower())
        call_model_mock.assert_not_called()
        audit_mock.assert_called()

    def test_deterministic_small_talk_does_not_swallow_specific_product_correction(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_small_talk_reply(
            {
                "agent": {"display_name": "Frabby Footwear Assistant"},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "I didn't ask for shoes, I asked for sandals.",
                "catalog": {"items": []},
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_small_talk_does_not_swallow_reset_plus_human_request(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_small_talk_reply(
            {
                "agent": {"display_name": "Frabby Footwear Assistant"},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "I didn't ask for anything yet, I want to talk to someone.",
                "catalog": {"items": []},
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_small_talk_does_not_swallow_reset_plus_shopping_request(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_small_talk_reply(
            {
                "agent": {"display_name": "Frabby Footwear Assistant"},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "I didn't ask for anything yet, I need sandals in size 42.",
                "catalog": {"items": []},
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_small_talk_does_not_swallow_reset_plus_delivery_question(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_small_talk_reply(
            {
                "agent": {"display_name": "Frabby Footwear Assistant"},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "I didn't ask for anything yet, what are your delivery slots?",
                "catalog": {"items": []},
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_asks_for_one_clarifying_detail_when_matches_are_empty(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "I need running shoes for the gym.",
                "catalog": {"items": []},
            }
        )

        self.assertIsNotNone(reply)
        self.assertFalse(reply["handoff_required"])
        self.assertEqual(reply["latest_intent"], "recommendation")
        self.assertIn("size", reply["reply_text"].lower())

    def test_extract_shopping_preferences_replaces_color_when_customer_changes_preference(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually I want white instead.",
            recent_context=[
                {"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"},
            ],
            existing_preferences={"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
        )

        self.assertEqual(preferences["colors"], ["white"])

    def test_extract_shopping_preferences_does_not_treat_hundred_as_red(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually I want something under one hundred for the same shoe.",
            recent_context=[],
            existing_preferences={},
        )

        self.assertNotIn("red", preferences["colors"])

    def test_extract_shopping_preferences_does_not_treat_air_max_model_number_as_budget(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Do you have the Air Max 90 in black?",
            recent_context=[],
            existing_preferences={},
        )

        self.assertEqual(preferences["max_budget"], "")
        self.assertEqual(preferences["price_preference"], "any")
        self.assertIn("air", preferences["product_terms"])
        self.assertIn("max", preferences["product_terms"])
        self.assertIn("black", preferences["colors"])

    def test_extract_shopping_preferences_allows_customer_to_replace_budget_with_premium_request(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually show me premium running shoes instead.",
            recent_context=[{"direction": "inbound", "text": "I need something under AED 200."}],
            existing_preferences={"max_budget": "200", "price_preference": "lower", "product_terms": ["running", "shoe"]},
        )

        self.assertEqual(preferences["max_budget"], "")
        self.assertEqual(preferences["price_preference"], "higher")

    def test_extract_shopping_preferences_does_not_treat_better_for_walking_as_premium_request(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Is this better for walking?",
            recent_context=[{"direction": "inbound", "text": "I need something under AED 200."}],
            existing_preferences={"max_budget": "200", "price_preference": "lower", "product_terms": ["running", "shoe"]},
        )

        self.assertEqual(preferences["max_budget"], "200")
        self.assertEqual(preferences["price_preference"], "lower")

    def test_extract_shopping_preferences_replaces_size_from_bare_follow_up_number(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually 43 instead.",
            recent_context=[{"direction": "inbound", "text": "Do you have this in EU 42?"}],
            existing_preferences={"sizes": ["42"]},
        )

        self.assertEqual(preferences["sizes"], ["43"])

    def test_extract_shopping_preferences_does_not_replace_size_with_delivery_minutes_on_switch_request(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually 43 minutes would be okay.",
            recent_context=[{"direction": "inbound", "text": "Do you have this in EU 42?"}],
            existing_preferences={"sizes": ["42"], "product_terms": ["running", "shoe"]},
        )

        self.assertEqual(preferences["sizes"], ["42"])

    def test_extract_shopping_preferences_non_product_turn_does_not_pollute_product_terms(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Can it arrive in 43 minutes?",
            recent_context=[{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
            existing_preferences={"product_terms": ["running", "shoe"], "colors": ["black"], "sizes": ["42"]},
        )

        self.assertIn("running", preferences["product_terms"])
        self.assertIn("shoe", preferences["product_terms"])
        self.assertNotIn("arrive", preferences["product_terms"])
        self.assertNotIn("minutes", preferences["product_terms"])

    def test_extract_shopping_preferences_keeps_existing_color_and_new_size_on_same_product_family_switch(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually I need a running shoe in EU 43 instead.",
            recent_context=[{"direction": "inbound", "text": "Do you have a black running shoe in EU 42 for daily running?"}],
            existing_preferences={
                "product_terms": ["running", "shoe"],
                "colors": ["black"],
                "sizes": ["42"],
                "use_case_terms": ["daily running"],
            },
        )

        self.assertEqual(preferences["sizes"], ["43"])
        self.assertEqual(preferences["colors"], ["black"])
        self.assertIn("daily running", preferences["use_case_terms"])

    def test_extract_shopping_preferences_clears_stale_size_on_product_family_switch(self) -> None:
        service = AIChatService(sessionmaker())

        preferences = service._extract_shopping_preferences(
            text="Actually I need a backpack instead.",
            recent_context=[{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
            existing_preferences={
                "product_terms": ["running", "shoe"],
                "colors": ["black"],
                "sizes": ["42"],
                "use_case_terms": ["daily running"],
            },
        )

        self.assertEqual(preferences["sizes"], [])
        self.assertEqual(preferences["colors"], [])
        self.assertIn("backpack", preferences["product_terms"])

    def test_catalog_search_terms_use_saved_preferences_for_follow_up_queries(self) -> None:
        service = AIChatService(sessionmaker())

        terms = service._catalog_search_terms(
            text="I need something cheaper under AED 200, still good for gym use. What do you recommend?",
            preferences={
                "product_terms": ["running", "shoe"],
                "colors": ["black"],
                "sizes": ["42"],
                "use_case_terms": ["daily running"],
            },
        )

        self.assertIn("running shoe", terms)
        self.assertIn("black", terms)
        self.assertIn("42", terms)

    def test_catalog_search_terms_drop_nonspecific_budget_only_tokens(self) -> None:
        service = AIChatService(sessionmaker())

        terms = service._catalog_search_terms(text="I need something under AED 200.", preferences={})

        self.assertNotIn("something", terms)
        self.assertNotIn("under", terms)
        self.assertNotIn("aed", terms)

    def test_catalog_search_terms_prioritize_current_product_switch_over_saved_terms(self) -> None:
        service = AIChatService(sessionmaker())

        terms = service._catalog_search_terms(
            text="Actually I need a backpack instead.",
            preferences={"product_terms": ["running", "shoe"], "colors": ["black"], "sizes": ["42"]},
        )

        self.assertIn("backpack", terms)
        self.assertLess(terms.index("backpack"), terms.index("running shoe"))

    def test_catalog_items_for_ai_matches_backpack_query_to_bag_product_name(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)
        client_id = str(new_uuid())
        product_id = str(new_uuid())
        variant_id = str(new_uuid())

        with session_factory() as session:
            session.add(
                ProductModel(
                    client_id=client_id,
                    product_id=product_id,
                    name="TravelPack Day Bag",
                    slug="travelpack-day-bag",
                    sku_root="TRAVELPACK",
                    brand="Frabby",
                    description="Compact day bag for daily use",
                    status="active",
                    default_price_amount=Decimal("149.00"),
                    min_price_amount=Decimal("129.00"),
                )
            )
            session.add(
                ProductVariantModel(
                    client_id=client_id,
                    variant_id=variant_id,
                    product_id=product_id,
                    title="Blue",
                    sku="TRAVELPACK-BLUE",
                    status="active",
                    price_amount=Decimal("149.00"),
                    min_price_amount=Decimal("129.00"),
                )
            )
            session.commit()

            preferences = service._extract_shopping_preferences(
                text="Actually I need a backpack instead.",
                recent_context=[{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
                existing_preferences={"product_terms": ["running", "shoe"], "colors": ["black"], "sizes": ["42"]},
            )

            with patch.object(service, "_stock_maps", return_value=({variant_id: Decimal("4")}, {})):
                items = service._catalog_items_for_ai(
                    session,
                    client_id,
                    "Actually I need a backpack instead.",
                    location_id=str(new_uuid()),
                    preferences=preferences,
                )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["product_name"], "TravelPack Day Bag")

    def test_catalog_items_for_ai_preserves_numbered_model_when_broad_matches_fill_candidate_pool(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)
        client_id = str(new_uuid())
        exact_product_id = str(new_uuid())
        exact_variant_id = str(new_uuid())
        stock_map: dict[str, Decimal] = {}

        with session_factory() as session:
            for prefix in ("Air Runner", "Max Runner"):
                for index in range(16):
                    product_id = str(new_uuid())
                    variant_id = str(new_uuid())
                    slug_base = prefix.lower().replace(" ", "-")
                    sku_base = prefix.upper().replace(" ", "-")
                    session.add(
                        ProductModel(
                            client_id=client_id,
                            product_id=product_id,
                            name=f"{prefix} {index:02d}",
                            slug=f"{slug_base}-{index:02d}",
                            sku_root=f"{sku_base}-{index:02d}",
                            brand="Frabby",
                            description="Black performance running shoe",
                            status="active",
                            default_price_amount=Decimal("199.00"),
                            min_price_amount=Decimal("179.00"),
                        )
                    )
                    session.add(
                        ProductVariantModel(
                            client_id=client_id,
                            variant_id=variant_id,
                            product_id=product_id,
                            title="Black / EU 42",
                            sku=f"{sku_base}-{index:02d}-BLK-42",
                            status="active",
                            price_amount=Decimal("199.00"),
                            min_price_amount=Decimal("179.00"),
                        )
                    )
                    stock_map[variant_id] = Decimal("5")

            session.add(
                ProductModel(
                    client_id=client_id,
                    product_id=exact_product_id,
                    name="Zoom Air Max 90",
                    slug="zoom-air-max-90",
                    sku_root="ZOOM-AIR-MAX-90",
                    brand="Frabby",
                    description="Black running shoe",
                    status="active",
                    default_price_amount=Decimal("289.00"),
                    min_price_amount=Decimal("259.00"),
                )
            )
            session.add(
                ProductVariantModel(
                    client_id=client_id,
                    variant_id=exact_variant_id,
                    product_id=exact_product_id,
                    title="Black / EU 42",
                    sku="ZOOM-AIR-MAX-90-BLK-42",
                    status="active",
                    price_amount=Decimal("289.00"),
                    min_price_amount=Decimal("259.00"),
                )
            )
            stock_map[exact_variant_id] = Decimal("5")
            session.commit()

            preferences = service._extract_shopping_preferences(
                text="Do you have the Air Max 90 in black?",
                recent_context=[],
                existing_preferences={},
            )

            with patch.object(service, "_stock_maps", return_value=(stock_map, {})):
                items = service._catalog_items_for_ai(
                    session,
                    client_id,
                    "Do you have the Air Max 90 in black?",
                    location_id=str(new_uuid()),
                    preferences=preferences,
                )

        self.assertTrue(any(item["product_name"] == "Zoom Air Max 90" for item in items))
        self.assertEqual(items[0]["product_name"], "Zoom Air Max 90")

    def test_catalog_items_for_ai_preserves_exact_named_product_even_when_over_budget(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)
        client_id = str(new_uuid())
        exact_product_id = str(new_uuid())
        exact_variant_id = str(new_uuid())
        other_product_id = str(new_uuid())
        other_variant_id = str(new_uuid())

        with session_factory() as session:
            session.add_all(
                [
                    ProductModel(
                        client_id=client_id,
                        product_id=exact_product_id,
                        name="Premium Runner",
                        slug="premium-runner",
                        sku_root="PREMIUM-RUNNER",
                        brand="Frabby",
                        description="High-cushion running shoe",
                        status="active",
                        default_price_amount=Decimal("350.00"),
                        min_price_amount=Decimal("300.00"),
                    ),
                    ProductModel(
                        client_id=client_id,
                        product_id=other_product_id,
                        name="Sprint Runner",
                        slug="sprint-runner",
                        sku_root="SPRINT-RUNNER",
                        brand="Frabby",
                        description="Daily running shoe",
                        status="active",
                        default_price_amount=Decimal("180.00"),
                        min_price_amount=Decimal("150.00"),
                    ),
                    ProductVariantModel(
                        client_id=client_id,
                        variant_id=exact_variant_id,
                        product_id=exact_product_id,
                        title="Black / EU 42",
                        sku="PREMIUM-RUNNER-BLK-42",
                        status="active",
                        price_amount=Decimal("350.00"),
                        min_price_amount=Decimal("300.00"),
                    ),
                    ProductVariantModel(
                        client_id=client_id,
                        variant_id=other_variant_id,
                        product_id=other_product_id,
                        title="Black / EU 42",
                        sku="SPRINT-RUNNER-BLK-42",
                        status="active",
                        price_amount=Decimal("180.00"),
                        min_price_amount=Decimal("150.00"),
                    ),
                ]
            )
            session.commit()

            preferences = service._extract_shopping_preferences(
                text="Do you have the Premium Runner in black under AED 200?",
                recent_context=[],
                existing_preferences={},
            )

            with patch.object(service, "_stock_maps", return_value=({exact_variant_id: Decimal("3"), other_variant_id: Decimal("5")}, {})):
                items = service._catalog_items_for_ai(
                    session,
                    client_id,
                    "Do you have the Premium Runner in black under AED 200?",
                    location_id=str(new_uuid()),
                    preferences=preferences,
                )

        product_names = [item["product_name"] for item in items]
        self.assertIn("Premium Runner", product_names)

    def test_catalog_items_for_ai_preserves_exact_named_product_even_when_out_of_stock(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)
        client_id = str(new_uuid())
        exact_product_id = str(new_uuid())
        exact_variant_id = str(new_uuid())
        other_product_id = str(new_uuid())
        other_variant_id = str(new_uuid())

        with session_factory() as session:
            session.add_all(
                [
                    ProductModel(
                        client_id=client_id,
                        product_id=exact_product_id,
                        name="SprintLite Trainer",
                        slug="sprintlite-trainer",
                        sku_root="SPRINTLITE-TRAINER",
                        brand="Frabby",
                        description="Affordable gym trainer",
                        status="active",
                        default_price_amount=Decimal("189.00"),
                        min_price_amount=Decimal("150.00"),
                    ),
                    ProductModel(
                        client_id=client_id,
                        product_id=other_product_id,
                        name="Power Trainer",
                        slug="power-trainer",
                        sku_root="POWER-TRAINER",
                        brand="Frabby",
                        description="Affordable gym trainer",
                        status="active",
                        default_price_amount=Decimal("189.00"),
                        min_price_amount=Decimal("150.00"),
                    ),
                    ProductVariantModel(
                        client_id=client_id,
                        variant_id=exact_variant_id,
                        product_id=exact_product_id,
                        title="Black / EU 42",
                        sku="SPRINTLITE-BLK-42",
                        status="active",
                        price_amount=Decimal("189.00"),
                        min_price_amount=Decimal("150.00"),
                    ),
                    ProductVariantModel(
                        client_id=client_id,
                        variant_id=other_variant_id,
                        product_id=other_product_id,
                        title="Black / EU 42",
                        sku="POWER-BLK-42",
                        status="active",
                        price_amount=Decimal("189.00"),
                        min_price_amount=Decimal("150.00"),
                    ),
                ]
            )
            session.commit()

            preferences = service._extract_shopping_preferences(
                text="Do you have the SprintLite Trainer in black?",
                recent_context=[],
                existing_preferences={},
            )

            with patch.object(service, "_stock_maps", return_value=({exact_variant_id: Decimal("0"), other_variant_id: Decimal("5")}, {})):
                items = service._catalog_items_for_ai(
                    session,
                    client_id,
                    "Do you have the SprintLite Trainer in black?",
                    location_id=str(new_uuid()),
                    preferences=preferences,
                )

        product_names = [item["product_name"] for item in items]
        self.assertIn("SprintLite Trainer", product_names)

    def test_rank_catalog_items_respects_color_word_boundaries(self) -> None:
        service = AIChatService(sessionmaker())

        ranked = service._rank_catalog_items_for_preferences(
            [
                {
                    "label": "Blue Budget Runner / Blue / EU 42",
                    "product_name": "Blue Budget Runner",
                    "variant_title": "Blue / EU 42",
                    "description": "A one hundred percent cotton trainer",
                    "unit_price": Decimal("99.00"),
                    "available_to_sell": Decimal("5"),
                    "can_sell": True,
                    "category": "Running Shoes",
                    "brand": "Frabby",
                },
                {
                    "label": "True Red Runner / Red / EU 42",
                    "product_name": "True Red Runner",
                    "variant_title": "Red / EU 42",
                    "description": "A real red trainer for daily running",
                    "unit_price": Decimal("129.00"),
                    "available_to_sell": Decimal("5"),
                    "can_sell": True,
                    "category": "Running Shoes",
                    "brand": "Frabby",
                },
            ],
            {"colors": ["red"], "product_terms": ["runner"], "sizes": ["42"]},
            limit=2,
        )

        self.assertEqual(ranked[0]["product_name"], "True Red Runner")

    def test_rank_catalog_items_prefers_higher_price_for_premium_request(self) -> None:
        service = AIChatService(sessionmaker())

        ranked = service._rank_catalog_items_for_preferences(
            [
                {
                    "label": "Value Runner / Black / EU 42",
                    "product_name": "Value Runner",
                    "variant_title": "Black / EU 42",
                    "description": "Reliable daily running shoe",
                    "unit_price": Decimal("180.00"),
                    "available_to_sell": Decimal("5"),
                    "can_sell": True,
                    "category": "Running Shoes",
                    "brand": "Frabby",
                },
                {
                    "label": "Premium Runner / Black / EU 42",
                    "product_name": "Premium Runner",
                    "variant_title": "Black / EU 42",
                    "description": "Premium cushioned running shoe",
                    "unit_price": Decimal("350.00"),
                    "available_to_sell": Decimal("5"),
                    "can_sell": True,
                    "category": "Running Shoes",
                    "brand": "Frabby",
                },
            ],
            {"colors": ["black"], "sizes": ["42"], "product_terms": ["runner"], "price_preference": "higher"},
            limit=2,
        )

        self.assertEqual(ranked[0]["product_name"], "Premium Runner")

    def test_deterministic_catalog_reply_does_not_hijack_non_shopping_follow_up(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "inbound", "text": "Do you have a black running shoe in EU 42 for daily running?"},
                        {"direction": "outbound", "text": "Yes, the AeroRun Flex Knit Running Shoe is AED 289.00."},
                    ],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "How long is delivery?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_non_product_available_question(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"},
                        {"direction": "outbound", "text": "Yes, I do."},
                    ],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "What delivery slots are available?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_non_product_budget_question(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "Is delivery under AED 20?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_delivery_question_even_with_product_details(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "What delivery slots are available for the black trainer in EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_product_qa_turns(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Show me black running shoes in EU 42."}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "Are these shoes comfortable for all-day walking?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_product_qa_turn_with_repeated_product_details(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have the black trainer in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["trainer"]},
                },
                "current_customer_message": "Is the black trainer in EU 42 good for walking?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_still_handles_walking_shoe_availability_query(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have walking shoes in black EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "CityWalk Comfort Shoe / Black / EU 42",
                            "product_name": "CityWalk Comfort Shoe",
                            "variant_title": "Black / EU 42",
                            "description": "Comfortable walking shoe for daily use",
                            "unit_price": Decimal("210.00"),
                            "available_to_sell": Decimal("3"),
                            "can_sell": True,
                            "category": "Walking Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertEqual(reply["latest_intent"], "availability")
        self.assertIn("CityWalk Comfort Shoe", reply["reply_text"])

    def test_deterministic_catalog_reply_size_only_first_turn_asks_product_question(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "Do you have size 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "Thunder Runner / Black / EU 42",
                            "product_name": "Thunder Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Daily running shoe",
                            "unit_price": Decimal("180.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("what product are you looking for", reply["reply_text"].lower())
        self.assertNotIn("Thunder Runner", reply["reply_text"])

    def test_deterministic_catalog_reply_budget_only_first_turn_asks_product_question(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "I need something under AED 200.",
                "catalog": {
                    "items": [
                        {
                            "label": "Thunder Runner / Black / EU 42",
                            "product_name": "Thunder Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Daily running shoe",
                            "unit_price": Decimal("180.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("what product are you looking for", reply["reply_text"].lower())
        self.assertNotIn("Thunder Runner", reply["reply_text"])

    def test_deterministic_catalog_reply_matches_running_shoe_query_to_trainer_variant(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have a black running shoe in EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("SprintLite Trainer", reply["reply_text"])
        self.assertNotIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_matches_compound_named_product_with_natural_spacing(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have the Sprint Lite Trainer in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("SprintLite Trainer", reply["reply_text"])
        self.assertNotIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_does_not_treat_eu_42_as_eu_42_point_5(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have a black running shoe in EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "AeroRun Running Shoe / Black / EU 42.5",
                            "product_name": "AeroRun Running Shoe",
                            "variant_title": "Black / EU 42.5",
                            "description": "Lightweight running shoe",
                            "unit_price": Decimal("229.00"),
                            "available_to_sell": Decimal("4"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("EU 42.5", reply["reply_text"])

    def test_deterministic_catalog_reply_does_not_parse_delivery_minutes_as_size(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "Can it arrive in 42 minutes?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_order_confirmation_turns(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have the black trainer in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["trainer"]},
                },
                "current_customer_message": "Yes, please place the order for the black EU 42 trainer. My name is John.",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_discount_negotiation_turn(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have the black trainer in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["trainer"]},
                },
                "current_customer_message": "Can you give me a better price on the black trainer in EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_skips_human_request_turn(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have the black trainer in EU 42?"}],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["trainer"]},
                },
                "current_customer_message": "Can I talk to someone about the black trainer in EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNone(reply)

    def test_deterministic_catalog_reply_still_handles_go_ahead_recommendation_turn(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"},
                        {"direction": "outbound", "text": "Yes, the AeroRun Flex Knit Running Shoe is AED 289.00."},
                    ],
                    "shopping_preferences": {"colors": ["black"], "sizes": ["42"], "product_terms": ["running", "shoe"]},
                },
                "current_customer_message": "Go ahead and show me something cheaper.",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "MotionCore Runner / Black / EU 42",
                            "product_name": "MotionCore Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Comfortable running shoe for gym and treadmill use",
                            "unit_price": Decimal("195.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertEqual(reply["latest_intent"], "recommendation")

    def test_deterministic_catalog_reply_handles_is_this_available_phrasing(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Tell me about the SprintLite Trainer."}],
                    "shopping_preferences": {"colors": ["black"], "product_terms": ["sprintlite", "trainer"]},
                },
                "current_customer_message": "Is this available in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertEqual(reply["latest_intent"], "availability")

    def test_deterministic_catalog_reply_pronoun_follow_up_does_not_switch_to_different_product(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Tell me about the SprintLite Trainer."}],
                    "shopping_preferences": {"colors": ["black"], "product_terms": ["sprintlite", "trainer"]},
                },
                "current_customer_message": "Is this available in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Power Trainer / Black / EU 42",
                            "product_name": "Power Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("Power Trainer", reply["reply_text"])

    def test_deterministic_catalog_reply_pronoun_follow_up_captures_requested_size(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Tell me about the SprintLite Trainer."}],
                    "shopping_preferences": {"product_terms": ["sprintlite", "trainer"]},
                },
                "current_customer_message": "Is this available in 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 39",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 39",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("EU 39 is available", reply["reply_text"])

    def test_deterministic_catalog_reply_pronoun_follow_up_without_anchor_asks_item_question(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "outbound", "text": "I can show you SprintLite Trainer or MotionCore Runner."},
                    ],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Is this available in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Power Trainer / Black / EU 42",
                            "product_name": "Power Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("which item are you asking about", reply["reply_text"].lower())
        self.assertNotIn("Power Trainer", reply["reply_text"])

    def test_deterministic_catalog_reply_uses_current_availability_intent_over_sticky_recommendation_flag(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [
                        {"direction": "inbound", "text": "What do you recommend for running shoes?"},
                        {"direction": "outbound", "text": "I can show you a few good options."},
                    ],
                    "shopping_preferences": {
                        "wants_recommendation": True,
                        "colors": ["black"],
                        "sizes": ["42"],
                        "product_terms": ["sprintlite", "trainer"],
                    },
                },
                "current_customer_message": "Do you have the SprintLite Trainer in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "MotionCore Runner / Black / EU 42",
                            "product_name": "MotionCore Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Comfortable running shoe for gym and treadmill use",
                            "unit_price": Decimal("195.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertEqual(reply["latest_intent"], "availability")
        self.assertNotIn("two good options", reply["reply_text"].lower())
        self.assertIn("SprintLite Trainer", reply["reply_text"])

    def test_deterministic_catalog_reply_does_not_claim_out_of_stock_item_is_available(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have a black running shoe in EU 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("0"),
                            "can_sell": False,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertNotIn("in stock", reply["reply_text"].lower())
        self.assertNotIn("is available", reply["reply_text"].lower())
        self.assertIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_does_not_substitute_wrong_color_or_size_match(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have a black running shoe in 42?"}],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have a black running shoe in 42?",
                "catalog": {
                    "items": [
                        {
                            "label": "Blue Budget Runner / Blue / EU 39",
                            "product_name": "Blue Budget Runner",
                            "variant_title": "Blue / EU 39",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("99.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("blue budget runner is available", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_does_not_substitute_wrong_color_name(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have yellow running shoes?"}],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have yellow running shoes?",
                "catalog": {
                    "items": [
                        {
                            "label": "Blue Budget Runner / Blue / EU 42",
                            "product_name": "Blue Budget Runner",
                            "variant_title": "Blue / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("99.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_does_not_substitute_wrong_product_family(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have sandals?"}],
                    "shopping_preferences": {"product_terms": ["running", "shoe"], "colors": ["black"], "sizes": ["42"]},
                },
                "current_customer_message": "Do you have sandals?",
                "catalog": {
                    "items": [
                        {
                            "label": "SprintLite Trainer / Black / EU 42",
                            "product_name": "SprintLite Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_product_switch_can_surface_non_black_backpack(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have a black running shoe in EU 42?"}],
                    "shopping_preferences": {"product_terms": ["running", "shoe"], "colors": ["black"], "sizes": ["42"]},
                },
                "current_customer_message": "Actually I need a backpack instead.",
                "catalog": {
                    "items": [
                        {
                            "label": "TravelPack Day Bag / Blue",
                            "product_name": "TravelPack Day Bag",
                            "variant_title": "Blue",
                            "description": "Compact backpack for daily use",
                            "unit_price": Decimal("149.00"),
                            "available_to_sell": Decimal("4"),
                            "can_sell": True,
                            "category": "Bags",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertNotIn("do not currently see", reply["reply_text"].lower())
        self.assertIn("TravelPack Day Bag", reply["reply_text"])

    def test_deterministic_catalog_reply_prefers_exact_numbered_product_match(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have the Air Max 90 in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Air Max 95 / Black",
                            "product_name": "Air Max 95",
                            "variant_title": "Black",
                            "description": "Classic runner",
                            "unit_price": Decimal("179.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "Air Max 90 / Black",
                            "product_name": "Air Max 90",
                            "variant_title": "Black",
                            "description": "Classic runner",
                            "unit_price": Decimal("199.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("Air Max 90", reply["reply_text"])
        self.assertNotIn("Air Max 95", reply["reply_text"])

    def test_deterministic_catalog_reply_does_not_substitute_wrong_numbered_product(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have the Air Max 90 in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Air Max 95 / Black",
                            "product_name": "Air Max 95",
                            "variant_title": "Black",
                            "description": "Classic runner",
                            "unit_price": Decimal("179.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("Air Max 95", reply["reply_text"])

    def test_deterministic_catalog_reply_does_not_substitute_partial_overlap_named_product(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have the Air Max in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Max Cushion Runner / Black",
                            "product_name": "Max Cushion Runner",
                            "variant_title": "Black",
                            "description": "Cushioned running shoe",
                            "unit_price": Decimal("199.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("Max Cushion Runner", reply["reply_text"])

    def test_deterministic_catalog_reply_does_not_substitute_partial_overlap_named_product_with_hint(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have the Air Trainer in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Air Jordan Trainer / Black",
                            "product_name": "Air Jordan Trainer",
                            "variant_title": "Black",
                            "description": "Cushioned trainer",
                            "unit_price": Decimal("199.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("Air Jordan Trainer", reply["reply_text"])

    def test_deterministic_catalog_reply_can_match_numbered_model_from_sku(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [],
                    "shopping_preferences": {},
                },
                "current_customer_message": "Do you have model 90 in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Air Max / Black",
                            "product_name": "Air Max",
                            "variant_title": "Black",
                            "sku": "AIR-MAX-90-BLK",
                            "description": "Classic runner",
                            "unit_price": Decimal("199.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertNotIn("do not currently see", reply["reply_text"].lower())
        self.assertIn("Air Max", reply["reply_text"])

    def test_deterministic_catalog_reply_named_product_switch_can_surface_backpack(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Do you have the Air Max 90 in black in EU 42?"}],
                    "shopping_preferences": {"product_terms": ["air", "max", "90"], "colors": ["black"], "sizes": ["42"]},
                },
                "current_customer_message": "Actually I need a backpack instead.",
                "catalog": {
                    "items": [
                        {
                            "label": "TravelPack Day Bag / Blue",
                            "product_name": "TravelPack Day Bag",
                            "variant_title": "Blue",
                            "description": "Compact backpack for daily use",
                            "unit_price": Decimal("149.00"),
                            "available_to_sell": Decimal("4"),
                            "can_sell": True,
                            "category": "Bags",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("TravelPack Day Bag", reply["reply_text"])
        self.assertNotIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_does_not_substitute_wrong_named_product(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {
                    "recent_messages": [{"direction": "inbound", "text": "Tell me about the SprintLite Trainer."}],
                    "shopping_preferences": {"product_terms": ["sprintlite", "trainer"], "colors": ["black"]},
                },
                "current_customer_message": "Do you have the SprintLite Trainer in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Power Trainer / Black / EU 42",
                            "product_name": "Power Trainer",
                            "variant_title": "Black / EU 42",
                            "description": "Affordable gym trainer for daily workouts",
                            "unit_price": Decimal("189.00"),
                            "available_to_sell": Decimal("6"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())

    def test_deterministic_catalog_reply_exact_budget_named_product_is_not_treated_as_price_intent(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "Do you have the Budget Runner in black?",
                "catalog": {
                    "items": [
                        {
                            "label": "Budget Runner / Black / EU 42",
                            "product_name": "Budget Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Entry-level running shoe",
                            "unit_price": Decimal("220.00"),
                            "available_to_sell": Decimal("4"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                        {
                            "label": "Sprint Runner / Black / EU 42",
                            "product_name": "Sprint Runner",
                            "variant_title": "Black / EU 42",
                            "description": "Daily running shoe",
                            "unit_price": Decimal("180.00"),
                            "available_to_sell": Decimal("5"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        },
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("Budget Runner", reply["reply_text"])
        self.assertNotIn("two good options", reply["reply_text"].lower())
        self.assertNotIn("Sprint Runner", reply["reply_text"])

    def test_deterministic_catalog_reply_exact_premium_named_product_still_respects_explicit_budget(self) -> None:
        service = AIChatService(sessionmaker())

        reply = service._deterministic_catalog_reply(
            {
                "business": {"currency_code": "AED", "currency_symbol": "AED"},
                "agent": {"handoff_message": "Our team will help from here."},
                "conversation": {"recent_messages": [], "shopping_preferences": {}},
                "current_customer_message": "Do you have the Premium Runner in black under AED 200?",
                "catalog": {
                    "items": [
                        {
                            "label": "Premium Runner / Black / EU 42",
                            "product_name": "Premium Runner",
                            "variant_title": "Black / EU 42",
                            "description": "High-cushion running shoe",
                            "unit_price": Decimal("350.00"),
                            "available_to_sell": Decimal("3"),
                            "can_sell": True,
                            "category": "Running Shoes",
                            "brand": "Frabby",
                        }
                    ]
                },
            }
        )

        self.assertIsNotNone(reply)
        self.assertIn("do not currently see", reply["reply_text"].lower())
        self.assertNotIn("Premium Runner / Black / EU 42 is available", reply["reply_text"])

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

    def test_technical_handoff_allows_reset_message_to_recover_and_reopen_conversation(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "technical-handoff-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-technical-handoff",
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
                    browser_session_id="browser-session-technical-handoff",
                    status="handoff",
                    handoff_reason="AI model request failed",
                )
            )
            session.commit()

        ai_reply = {
            "reply_text": "You’re right — sorry about that. Tell me what you are looking for, your size, and any color or budget preference, and I’ll help from here.",
            "handoff_required": False,
            "handoff_reason": "",
            "order_status": None,
            "latest_intent": "other",
            "latest_summary": "I didn’t ask for anything yet.",
            "ai_metadata": {"ai_runtime": "easy_ecom"},
        }

        with patch.object(service, "_invoke_easy_ecom_ai", return_value=ai_reply) as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-technical-handoff",
                client_message_id="msg-technical-handoff-001",
                message="I didn’t ask for anything yet.",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_called_once()
        self.assertEqual(result["status"], "open")
        self.assertFalse(result["handoff_required"])
        self.assertEqual(result["handoff_reason"], "")

    def test_technical_handoff_allows_reset_plus_shopping_request_to_recover(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "technical-handoff-shopping-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-technical-handoff-shopping",
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
                    browser_session_id="browser-session-technical-handoff-shopping",
                    status="handoff",
                    handoff_reason="AI model request failed",
                )
            )
            session.commit()

        ai_reply = {
            "reply_text": "Yes — we have sandals in size 42.",
            "handoff_required": False,
            "handoff_reason": "",
            "order_status": None,
            "latest_intent": "availability",
            "latest_summary": "Customer asked for sandals in size 42.",
            "ai_metadata": {"ai_runtime": "easy_ecom"},
        }

        with patch.object(service, "_invoke_easy_ecom_ai", return_value=ai_reply) as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-technical-handoff-shopping",
                client_message_id="msg-technical-handoff-shopping-001",
                message="I didn’t ask for anything yet, I need sandals in size 42.",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_called_once()
        self.assertEqual(result["status"], "open")
        self.assertFalse(result["handoff_required"])
        self.assertEqual(result["handoff_reason"], "")

    def test_technical_handoff_does_not_reopen_on_reset_plus_delivery_question(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "technical-handoff-delivery-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-technical-handoff-delivery",
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
                    browser_session_id="browser-session-technical-handoff-delivery",
                    status="handoff",
                    handoff_reason="AI model request failed",
                )
            )
            session.commit()

        with patch.object(service, "_invoke_easy_ecom_ai") as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-technical-handoff-delivery",
                client_message_id="msg-technical-handoff-delivery-001",
                message="I didn’t ask for anything yet, what are your delivery slots?",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_not_called()
        self.assertEqual(result["status"], "handoff")
        self.assertTrue(result["handoff_required"])
        self.assertEqual(result["handoff_reason"], "AI model request failed")

    def test_technical_handoff_does_not_reopen_on_reset_plus_apology(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "technical-handoff-apology-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-technical-handoff-apology",
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
                    browser_session_id="browser-session-technical-handoff-apology",
                    status="handoff",
                    handoff_reason="AI model request failed",
                )
            )
            session.commit()

        with patch.object(service, "_invoke_easy_ecom_ai") as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-technical-handoff-apology",
                client_message_id="msg-technical-handoff-apology-001",
                message="I didn’t ask for anything yet, sorry.",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_not_called()
        self.assertEqual(result["status"], "handoff")
        self.assertTrue(result["handoff_required"])
        self.assertEqual(result["handoff_reason"], "AI model request failed")

    def test_model_requested_handoff_does_not_reopen_on_greeting(self) -> None:
        engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(engine)
        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
        service = AIChatService(session_factory)

        client_id = str(uuid4())
        profile_id = new_uuid()
        channel_id = new_uuid()
        conversation_id = new_uuid()
        widget_key = "model-requested-handoff-widget-key"

        with session_factory() as session:
            session.add(
                ClientModel(
                    client_id=client_id,
                    slug="tenant-store-model-requested-handoff",
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
                    browser_session_id="browser-session-model-requested-handoff",
                    status="handoff",
                    handoff_reason="AI model requested handoff",
                )
            )
            session.commit()

        with patch.object(service, "_invoke_easy_ecom_ai") as invoke_mock:
            result = service.handle_public_message(
                widget_key=widget_key,
                browser_session_id="browser-session-model-requested-handoff",
                client_message_id="msg-model-requested-handoff-001",
                message="Hi",
                customer=None,
                metadata={"source": "unit_test"},
                origin="",
                client_ip="127.0.0.1",
                trusted_origins=None,
            )

        invoke_mock.assert_not_called()
        self.assertEqual(result["status"], "handoff")
        self.assertTrue(result["handoff_required"])
        self.assertEqual(result["handoff_reason"], "AI model requested handoff")


if __name__ == "__main__":
    unittest.main()
