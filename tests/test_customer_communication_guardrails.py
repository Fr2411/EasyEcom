from __future__ import annotations

from decimal import Decimal
import json
import unittest
from unittest.mock import Mock, patch

import httpx
from easy_ecom.data.store.postgres_models import AssistantPlaybookModel, CustomerConversationModel
from easy_ecom.domain.services.customer_communication_service import CustomerCommunicationService, NvidiaChatClient


class CustomerCommunicationGuardrailTests(unittest.TestCase):
    def setUp(self) -> None:
        self.service = CustomerCommunicationService(lambda: None)  # type: ignore[arg-type]

    def _playbook(self, business_type: str = "general_retail") -> AssistantPlaybookModel:
        return AssistantPlaybookModel(
            playbook_id="00000000-0000-0000-0000-000000000001",
            client_id="00000000-0000-0000-0000-000000000002",
            business_type=business_type,
            brand_personality="friendly",
        )

    def test_nvidia_client_falls_back_to_nemotron_on_primary_timeout(self) -> None:
        client = NvidiaChatClient()
        client.base_url = "https://example.test/v1"
        client.api_key = "test-key"
        client.model = "google/gemma-4-31b-it"
        client.fallback_model = "nvidia/nemotron-3-super-120b-a12b"
        client.primary_timeout_seconds = 1
        client.fallback_timeout_seconds = 7

        fallback_response = Mock()
        fallback_response.raise_for_status.return_value = None
        fallback_response.json.return_value = {"choices": [{"message": {"content": "Fallback reply"}}]}

        with patch(
            "easy_ecom.domain.services.customer_communication_service.httpx.post",
            side_effect=[httpx.ReadTimeout("primary timed out"), fallback_response],
        ) as post:
            payload = client.create_chat_completion(messages=[{"role": "user", "content": "Hi"}], tools=[])

        self.assertEqual(post.call_args_list[0].kwargs["json"]["model"], "google/gemma-4-31b-it")
        self.assertEqual(post.call_args_list[0].kwargs["timeout"], 1)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["model"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(post.call_args_list[1].kwargs["timeout"], 7)
        self.assertEqual(payload["_easy_ecom_model_name"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(payload["_easy_ecom_fallback_from"], "google/gemma-4-31b-it")

    def test_price_answer_requires_tool_grounding(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="How much is the salmon dog food?",
            response_text="It is 50 AED.",
            tool_names=[],
            playbook=self._playbook(),
        )
        self.assertEqual(status, "escalated")
        self.assertIn("without tool grounding", reason)

    def test_clarifying_question_can_avoid_grounding(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="How much is the salmon dog food?",
            response_text="Which size would you like?",
            tool_names=[],
            playbook=self._playbook(),
        )
        self.assertEqual(status, "ok")
        self.assertEqual(reason, "")

    def test_pet_health_reply_needs_veterinarian_safe_handling(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="My dog is vomiting. Which food should I buy?",
            response_text="Try our chicken food today.",
            tool_names=["search_catalog_variants"],
            playbook=self._playbook("pet_food"),
        )
        self.assertEqual(status, "escalated")
        self.assertIn("Pet health concern", reason)

    def test_pet_health_vet_language_is_allowed(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="My dog is vomiting. Which food should I buy?",
            response_text="For vomiting, please check with a veterinarian first. What food is your dog eating now?",
            tool_names=[],
            playbook=self._playbook("pet_food"),
        )
        self.assertEqual(status, "ok")
        self.assertEqual(reason, "")

    def test_catalog_search_query_removes_service_words(self) -> None:
        queries = self.service._catalog_search_queries("Hi, do you have test2 in stock and what is the price?")

        self.assertGreaterEqual(len(queries), 1)
        self.assertEqual(queries[0], "test2")

    def test_grounded_price_stock_reply_uses_tool_facts(self) -> None:
        reply = self.service._compose_catalog_grounded_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=self._playbook("pet_food"),
            conversation=CustomerConversationModel(memory_json={}),
            inbound_text="Do you have test2 in stock and what is the price?",
            grounding=type(
                "Grounding",
                (),
                {
                    "query": "test2",
                    "search_result": {
                        "items": [
                            {
                                "label": "test2",
                                "sku": "TEST2",
                                "available_to_sell": "9.000",
                                "unit_price": "120.00",
                            }
                        ]
                    },
                    "availability_result": {
                        "variant": {
                            "label": "test2",
                            "sku": "TEST2",
                            "available_to_sell": "9.000",
                            "unit_price": "120.00",
                        }
                    },
                    "price_result": {
                        "variant": {
                            "label": "test2",
                            "sku": "TEST2",
                            "unit_price": "120.00",
                        }
                    },
                },
            )(),
        )

        self.assertIn("test2", reply)
        self.assertIn("available", reply)
        self.assertIn("$120.00", reply)
        self.assertIn("draft order", reply)

    def test_format_money_spaces_alphabetic_currency_symbols(self) -> None:
        self.assertEqual(
            self.service._format_money(
                "289.00",
                type("Client", (), {"currency_symbol": "AED ", "currency_code": "AED"})(),
            ),
            "AED 289.00",
        )

    def test_pet_health_playbook_reply_is_veterinarian_safe(self) -> None:
        reply = self.service._deterministic_playbook_reply(
            client=type("Client", (), {"business_name": "Pet Shop"})(),
            playbook=self._playbook("pet_food"),
            inbound_text="My dog is vomiting. Which food should I buy?",
        )

        self.assertIn("veterinarian", reply)
        self.assertIn("current diet", reply)
        self.assertIn("health concerns", reply)

    def test_pet_recommendation_asks_template_questions(self) -> None:
        reply = self.service._deterministic_playbook_reply(
            client=type("Client", (), {"business_name": "Pet Shop"})(),
            playbook=self._playbook("pet_food"),
            inbound_text="Can you recommend food for my puppy?",
        )

        self.assertIn("age", reply)
        self.assertIn("allergies", reply)
        self.assertIn("health concerns", reply)

    def test_shoe_store_recommendation_asks_sales_questions(self) -> None:
        reply = self.service._deterministic_playbook_reply(
            client=type("Client", (), {"business_name": "Shoe Shop"})(),
            playbook=self._playbook("shoe_store"),
            inbound_text="I need shoes for work. Can you recommend something?",
        )

        self.assertIn("shoe size", reply)
        self.assertTrue("color" in reply or "preferred color" in reply)
        self.assertIn("budget", reply)

    def test_each_vertical_recommendation_asks_domain_questions(self) -> None:
        cases = {
            "fashion": ("Can you suggest something for an office party?", ("size", "occasion", "budget")),
            "electronics": ("Which charger should I buy?", ("device model", "compatibility", "warranty")),
            "cosmetics": ("Can you recommend a serum?", ("skin type", "allergies", "desired result")),
            "grocery": ("What should I buy for breakfast?", ("quantity", "brand", "dietary restrictions")),
        }
        for business_type, (message, expected_terms) in cases.items():
            with self.subTest(business_type=business_type):
                reply = self.service._deterministic_playbook_reply(
                    client=type("Client", (), {"business_name": "Demo Shop"})(),
                    playbook=self._playbook(business_type),
                    inbound_text=message,
                )
                for term in expected_terms:
                    self.assertIn(term, reply)

    def test_cosmetics_allergy_reply_is_limited_and_safe(self) -> None:
        reply = self.service._deterministic_playbook_reply(
            client=type("Client", (), {"business_name": "Glow Shop"})(),
            playbook=self._playbook("cosmetics"),
            inbound_text="My skin is sensitive and I get rashes. Which cream is best?",
        )

        self.assertIn("qualified professional", reply)
        self.assertIn("known allergies", reply)

    def test_electronics_safety_concern_escalates(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="My charger is smoking and the battery is swollen. What should I buy?",
            response_text="Buy a 65W charger.",
            tool_names=[],
            playbook=self._playbook("electronics"),
        )

        self.assertEqual(status, "escalated")
        self.assertIn("Electronics safety concern", reason)

    def test_electronics_safety_escalation_gives_immediate_instruction(self) -> None:
        reply = self.service._safe_escalation_text(
            "Circuit House",
            "My charger is smoking and the battery is swollen.",
        )

        self.assertIn("stop using", reply)
        self.assertIn("unplug", reply)
        self.assertIn("team member", reply)

    def test_catalog_item_scoring_resolves_shoe_size_color_brand(self) -> None:
        selected = self.service._select_best_catalog_item(
            "Do you have black AeroRun size 42?",
            [
                {
                    "variant_id": "1",
                    "label": "CloudStep Daily Sneaker / EU 42 / Black",
                    "sku": "CSD-42-BLK",
                    "product_name": "CloudStep Daily Sneaker",
                    "brand": "CloudStep",
                },
                {
                    "variant_id": "2",
                    "label": "AeroRun Flex Knit Running Shoe / EU 42 / Black",
                    "sku": "ARF-42-BLK",
                    "product_name": "AeroRun Flex Knit Running Shoe",
                    "brand": "AeroRun",
                },
            ],
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected["sku"], "ARF-42-BLK")

    def test_fashion_memory_extracts_preferences_and_contact(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={},
            external_sender_name="",
            external_sender_phone="",
            external_sender_email="",
        )

        self.service._remember_inbound_context(
            conversation,
            self._playbook("fashion"),
            "I am size M, prefer neutral colors, under AED 250. My name is Dana, phone +971501234000.",
        )

        memory = conversation.memory_json or {}
        self.assertEqual(memory["preferences"]["size"], "M")
        self.assertEqual(memory["preferences"]["budget"], "250")
        self.assertIn("neutral", memory["preferences"]["colors"])
        self.assertEqual(memory["customer_contact"]["name"], "Dana")
        self.assertIn("+971501234000", memory["customer_contact"]["phone"])

    def test_buyer_archetype_detects_budget_and_repeat_buyers(self) -> None:
        budget_conversation = CustomerConversationModel(memory_json={"preferences": {"budget": "250"}})
        repeat_conversation = CustomerConversationModel(memory_json={"thread_graph": {"restored_from_conversation_id": "prev-1"}})

        self.assertEqual(
            self.service._buyer_archetype(budget_conversation, "Anything cheaper?"),
            "budget_buyer",
        )
        self.assertEqual(
            self.service._buyer_archetype(repeat_conversation, "I need another pair"),
            "repeat_buyer",
        )

    def test_lead_context_is_extracted_from_campaign_reference(self) -> None:
        conversation = CustomerConversationModel(memory_json={})

        self.service._remember_inbound_context(
            conversation,
            self._playbook("shoe_store"),
            "Hi, I came from your Instagram ad and I need black office shoes in size 42.",
        )

        memory = conversation.memory_json or {}
        self.assertEqual(memory["lead_context"]["source"], "instagram")
        self.assertEqual(memory["lead_context"]["source_type"], "campaign")
        self.assertEqual(memory["customer_journey"]["lead_source"], "instagram")

    def test_sales_progress_reply_compares_recent_choices_naturally(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "preferences": {"size": "42", "occasion": "work", "budget": "250"},
                "recent_choices": [
                    {"label": "Ariya Soft Blazer / 42 / Black", "sku": "ASB-42-BLK", "unit_price": "219.00", "available_to_sell": "11.000"},
                    {"label": "City Oxford Knit / 42 / Black", "sku": "COK-42-BLK", "unit_price": "199.00", "available_to_sell": "8.000"},
                ],
            }
        )

        reply = self.service._sales_progress_reply(
            client=type("Client", (), {"currency_symbol": "AED ", "currency_code": "AED"})(),
            conversation=conversation,
            inbound_text="Which one is better?",
        )

        self.assertIn("Between Ariya Soft Blazer", reply)
        self.assertIn("City Oxford Knit", reply)
        self.assertIn("I’d lean", reply)

    def test_sales_progress_reply_uses_premium_positioning_for_quality_buyer(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "buyer_archetype": "premium_buyer",
                "preferences": {"size": "42", "occasion": "work"},
                "recent_choices": [
                    {"label": "Ariya Soft Blazer / 42 / Black", "sku": "ASB-42-BLK", "unit_price": "219.00", "available_to_sell": "11.000"},
                    {"label": "City Oxford Knit / 42 / Black", "sku": "COK-42-BLK", "unit_price": "199.00", "available_to_sell": "8.000"},
                ],
            }
        )

        reply = self.service._sales_progress_reply(
            client=type("Client", (), {"currency_symbol": "AED ", "currency_code": "AED"})(),
            conversation=conversation,
            inbound_text="Which one is better quality?",
        )

        self.assertIn("stronger overall pick", reply)
        self.assertIn("quality", reply.lower())

    def test_sales_progress_reply_handles_hesitation_with_soft_close(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "lead_context": {"source": "instagram", "source_type": "campaign"},
                "sales_state": {"focus_label": "Trail Runner / M / Black"},
            }
        )

        reply = self.service._sales_progress_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            conversation=conversation,
            inbound_text="Looks good but I will think about it and maybe later.",
        )

        self.assertIn("take your time", reply.lower())
        self.assertIn("Trail Runner / M / Black", reply)
        self.assertIn("draft order", reply)

    def test_language_instruction_uses_stored_language_hint(self) -> None:
        conversation = CustomerConversationModel(memory_json={"language_hint": "arabic"})

        instruction = self.service._language_instruction(conversation)

        self.assertIn("Reply in Arabic", instruction)

    def test_negotiation_progress_reply_uses_discount_policy_without_promising(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "sales_state": {"focus_label": "Trail Runner / M / Black", "last_offered_price": "79.00"},
                "buyer_archetype": "budget_buyer",
            }
        )
        playbook = self._playbook("shoe_store")
        playbook.policy_json = {"discounts": "Discounts are staff-approved only."}

        reply = self.service._negotiation_progress_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=playbook,
            conversation=conversation,
            inbound_text="What is your best price?",
        )

        self.assertIn("$79.00", reply)
        self.assertIn("staff-approved", reply)
        self.assertIn("lower-price alternative", reply)

    def test_negotiation_progress_reply_handles_expensive_signal(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "sales_state": {"focus_label": "Trail Runner / M / Black"},
                "buyer_archetype": "campaign_buyer",
            }
        )
        reply = self.service._negotiation_progress_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=self._playbook("shoe_store"),
            conversation=conversation,
            inbound_text="Looks expensive for me.",
        )

        self.assertIn("lower-price alternative", reply)
        self.assertIn("Trail Runner / M / Black", reply)

    def test_negotiation_progress_reply_supports_bundle_interest(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "sales_state": {"focus_label": "Trail Runner / M / Black"},
            }
        )
        playbook = self._playbook("shoe_store")
        playbook.sales_goals_json = {"cross_sell": True}
        reply = self.service._negotiation_progress_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=playbook,
            conversation=conversation,
            inbound_text="Any socks or care kit to go with it?",
        )

        self.assertIn("matching socks, care items, or insoles", reply)
        self.assertIn("practical", reply)

    def test_negotiation_progress_reply_repeated_best_price_reduces_looping(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "sales_state": {"focus_label": "Trail Runner / M / Black", "last_offered_price": "79.00"},
                "negotiation_state": {"best_price_asked_count": 1},
            }
        )
        playbook = self._playbook("shoe_store")
        playbook.policy_json = {"discounts": "Discounts are staff-approved only."}

        reply = self.service._negotiation_progress_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=playbook,
            conversation=conversation,
            inbound_text="Can you do better price?",
        )

        self.assertIn("I don’t want to drag you in circles", reply)
        self.assertIn("draft order", reply)

    def test_sales_progress_reply_updates_hesitation_memory(self) -> None:
        conversation = CustomerConversationModel(memory_json={"sales_state": {"focus_label": "Trail Runner / M / Black"}})

        self.service._sales_progress_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            conversation=conversation,
            inbound_text="Maybe later, I will think about it.",
        )

        memory = conversation.memory_json or {}
        self.assertEqual(memory["negotiation_state"]["stall_count"], 1)
        self.assertEqual(memory["negotiation_state"]["last_move"], "hesitation_soft_hold")

    def test_language_hint_detects_arabic_text(self) -> None:
        self.assertEqual(self.service._detect_language_hint("مرحبا، أريد حذاء أسود"), "arabic")

    def test_media_context_reply_asks_for_focus_detail_without_fake_vision(self) -> None:
        conversation = CustomerConversationModel(memory_json={"message_modality": {"has_image": True}})

        reply = self.service._media_context_reply(
            conversation=conversation,
            inbound_text="See attached screenshot, what do you think?",
        )

        self.assertIn("image or screenshot", reply)
        self.assertIn("product name", reply)

    def test_remember_inbound_context_stores_language_and_modality(self) -> None:
        conversation = CustomerConversationModel(memory_json={})

        self.service._remember_inbound_context(
            conversation,
            self._playbook("shoe_store"),
            "مرحبا، see attached screenshot",
            metadata={"attachments": ["image/png"]},
        )

        memory = conversation.memory_json or {}
        self.assertEqual(memory["language_hint"], "arabic")
        self.assertTrue(memory["message_modality"]["has_image"])

    def test_grounded_price_reply_respects_budget_buyer_style(self) -> None:
        conversation = CustomerConversationModel(memory_json={"buyer_archetype": "budget_buyer"})

        reply = self.service._compose_catalog_grounded_reply(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=self._playbook("shoe_store"),
            conversation=conversation,
            inbound_text="How much is Ariya Soft Blazer?",
            grounding=type(
                "Grounding",
                (),
                {
                    "query": "Ariya Soft Blazer",
                    "search_result": {
                        "items": [
                            {
                                "label": "Ariya Soft Blazer / 42 / Black",
                                "sku": "ASB-42-BLK",
                                "available_to_sell": "11.000",
                                "unit_price": "219.00",
                            }
                        ]
                    },
                    "availability_result": {
                        "variant": {
                            "label": "Ariya Soft Blazer / 42 / Black",
                            "sku": "ASB-42-BLK",
                            "available_to_sell": "11.000",
                            "unit_price": "219.00",
                        }
                    },
                    "price_result": {
                        "variant": {
                            "label": "Ariya Soft Blazer / 42 / Black",
                            "sku": "ASB-42-BLK",
                            "unit_price": "219.00",
                        }
                    },
                },
            )(),
        )

        self.assertIn("closest lower-price alternative", reply)

    def test_previous_variant_context_supports_it_and_price_again(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "last_variant": {
                    "variant_id": "variant-1",
                    "label": "Ariya Soft Blazer / M / Sand",
                    "sku": "ALB-M-SAND",
                    "location_id": "location-1",
                }
            }
        )

        remembered = self.service._remembered_variant_for_message(conversation, "What was the price again, and can I return it?")

        self.assertIsNotNone(remembered)
        self.assertEqual(remembered["sku"], "ALB-M-SAND")

    def test_previous_variant_context_supports_draft_order_request(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "last_variant": {
                    "variant_id": "variant-1",
                    "label": "AeroRun Flex Knit Running Shoe / EU 42 / Black",
                    "sku": "ARF-42-BLK",
                    "location_id": "location-1",
                }
            }
        )

        remembered = self.service._remembered_variant_for_message(
            conversation,
            "Looks good. Please prepare a draft order. My name is Samir, phone +971501110001.",
        )

        self.assertIsNotNone(remembered)
        self.assertEqual(remembered["sku"], "ARF-42-BLK")

    def test_recent_choice_context_supports_first_option(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "recent_choices": [
                    {"variant_id": "variant-1", "label": "Ariya Soft Blazer / M / Sand", "sku": "ALB-M-SAND"},
                    {"variant_id": "variant-2", "label": "Minimal Oxford Shirt / M / White", "sku": "MWO-M-WHT"},
                ]
            }
        )

        remembered = self.service._remembered_variant_for_message(conversation, "What is the price for the first one?")

        self.assertIsNotNone(remembered)
        self.assertEqual(remembered["sku"], "ALB-M-SAND")

    def test_catalog_choice_memory_is_json_serializable(self) -> None:
        conversation = CustomerConversationModel(memory_json={})

        self.service._remember_catalog_choices(
            conversation,
            [
                {
                    "variant_id": "variant-1",
                    "label": "Ariya Soft Blazer / M / Sand",
                    "sku": "ALB-M-SAND",
                    "unit_price": Decimal("219.00"),
                    "available_to_sell": Decimal("11.000"),
                }
            ],
        )

        json.dumps(conversation.memory_json)
        self.assertEqual(conversation.memory_json["recent_choices"][0]["unit_price"], "219.00")
        self.assertEqual(conversation.memory_json["sales_state"]["offer_state"], "recommendation_ready")

    def test_merge_memory_keeps_existing_and_adds_new_graph_state(self) -> None:
        merged = self.service._merge_memory(
            {"preferences": {"size": "M"}, "recent_choices": [{"sku": "A"}]},
            {"preferences": {"colors": ["black"]}, "recent_choices": [{"sku": "B"}], "sales_state": {"focus_label": "Trail Runner"}},
        )

        self.assertEqual(merged["preferences"]["size"], "M")
        self.assertIn("black", merged["preferences"]["colors"])
        self.assertEqual(merged["recent_choices"][0]["sku"], "B")
        self.assertEqual(merged["sales_state"]["focus_label"], "Trail Runner")

    def test_policy_answer_uses_structured_playbook_policy(self) -> None:
        playbook = self._playbook("fashion")
        playbook.policy_json = {"returns": "Exchange or return within 7 days if unused and tags are attached."}

        reply = self.service._deterministic_policy_reply(
            playbook=playbook,
            inbound_text="Can I return it if it does not fit?",
        )

        self.assertIn("Return policy", reply)
        self.assertIn("7 days", reply)

    def test_policy_answer_can_include_multiple_policy_sections(self) -> None:
        playbook = self._playbook("shoe_store")
        playbook.policy_json = {
            "delivery": "Delivery takes 1-3 business days after confirmation.",
            "payment": "Staff sends payment links after draft order review.",
        }

        reply = self.service._deterministic_policy_reply(
            playbook=playbook,
            inbound_text="What is your delivery time and payment policy?",
        )

        self.assertIn("Delivery policy", reply)
        self.assertIn("Payment policy", reply)

    def test_discount_policy_is_not_blocked_by_buy_language(self) -> None:
        playbook = self._playbook("shoe_store")
        playbook.policy_json = {"discounts": "Discounts are staff-approved only."}

        reply = self.service._deterministic_policy_reply(
            playbook=playbook,
            inbound_text="Do you give discounts if I buy shoes and the care kit together?",
        )

        self.assertIn("Discount policy", reply)
        self.assertIn("staff-approved", reply)

    def test_fashion_recommendation_waits_for_size_before_scoring(self) -> None:
        playbook = self._playbook("fashion")

        self.assertFalse(
            self.service._has_enough_recommendation_preferences(
                playbook,
                {"occasion": "office party", "colors": ["neutral"]},
            )
        )
        self.assertTrue(
            self.service._has_enough_recommendation_preferences(
                playbook,
                {"size": "M", "occasion": "office party", "colors": ["neutral"], "budget": "250"},
            )
        )

    def test_lookup_language_can_trigger_catalog_grounding(self) -> None:
        self.assertTrue(self.service._needs_catalog_grounding("Actually check the white MetroCourt in EU 41 too."))


if __name__ == "__main__":
    unittest.main()
