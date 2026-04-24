from __future__ import annotations

import unittest

from easy_ecom.data.store.postgres_models import AssistantPlaybookModel, CustomerConversationModel
from easy_ecom.domain.services.customer_communication_service import CustomerCommunicationService


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

        self.assertIn("I checked test2", reply)
        self.assertIn("9 available", reply)
        self.assertIn("$120.00", reply)

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
        self.assertIn("preferred color", reply)
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

    def test_policy_answer_uses_structured_playbook_policy(self) -> None:
        playbook = self._playbook("fashion")
        playbook.policy_json = {"returns": "Exchange or return within 7 days if unused and tags are attached."}

        reply = self.service._deterministic_policy_reply(
            playbook=playbook,
            inbound_text="Can I return it if it does not fit?",
        )

        self.assertIn("Return policy", reply)
        self.assertIn("7 days", reply)

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


if __name__ == "__main__":
    unittest.main()
