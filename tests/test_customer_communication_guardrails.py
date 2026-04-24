from __future__ import annotations

import unittest

from easy_ecom.data.store.postgres_models import AssistantPlaybookModel
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


if __name__ == "__main__":
    unittest.main()
