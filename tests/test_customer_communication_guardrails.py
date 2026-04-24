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


if __name__ == "__main__":
    unittest.main()
