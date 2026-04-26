from __future__ import annotations

from decimal import Decimal
import json
import unittest
from unittest.mock import Mock, patch

import httpx

from easy_ecom.data.store.postgres_models import AssistantPlaybookModel, AssistantRunModel, CustomerConversationModel
from easy_ecom.domain.services.customer_communication_service import (
    CatalogGrounding,
    CustomerCommunicationService,
    NvidiaChatClient,
    PreparedReplyContext,
)


class FakeChatClient:
    provider = "fake"
    model = "fake-composer"
    is_configured = True

    def __init__(self, reply: str | list[str] = "Model-composed customer reply") -> None:
        self.replies = reply if isinstance(reply, list) else [reply]
        self.calls: list[dict[str, object]] = []

    def create_chat_completion(self, *, messages: list[dict[str, object]], tools: list[dict[str, object]]) -> dict[str, object]:
        self.calls.append({"messages": messages, "tools": tools})
        reply = self.replies[min(len(self.calls) - 1, len(self.replies) - 1)]
        return {
            "_easy_ecom_model_name": self.model,
            "choices": [{"message": {"content": reply}}],
            "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        }


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

    def _client(self):
        return type("Client", (), {"business_name": "Frabby Footwear", "currency_symbol": "AED ", "currency_code": "AED"})()

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
        self.assertNotIn("tools", post.call_args_list[0].kwargs["json"])
        self.assertEqual(post.call_args_list[0].kwargs["timeout"], 1)
        self.assertEqual(post.call_args_list[1].kwargs["json"]["model"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(post.call_args_list[1].kwargs["timeout"], 7)
        self.assertEqual(payload["_easy_ecom_model_name"], "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(payload["_easy_ecom_fallback_from"], "google/gemma-4-31b-it")

    def test_model_composer_receives_context_and_no_tools(self) -> None:
        fake_client = FakeChatClient("Yes, MetroWalk is available at AED 239.00.")
        service = CustomerCommunicationService(lambda: None, ai_client=fake_client)  # type: ignore[arg-type]
        run = AssistantRunModel(prompt_snapshot_json={})
        prepared = PreparedReplyContext(
            kind="catalog_grounded_answer",
            next_best_action="answer_grounded_fact_then_offer_one_next_step",
            facts={
                "selected_variant": {
                    "label": "MetroWalk Office Loafer / EU 42 / Black",
                    "sku": "MWL-42-BLK",
                    "unit_price": {"display": "AED 239.00"},
                    "available_to_sell": "3",
                }
            },
            tool_names=("search_catalog_variants", "get_variant_availability", "get_variant_price"),
        )

        reply, usage = service._compose_model_customer_reply(
            client=self._client(),
            playbook=self._playbook("shoe_store"),
            channel=type("Channel", (), {"provider": "website"})(),
            conversation=CustomerConversationModel(memory_json={}),
            inbound=type("Inbound", (), {"message_text": "Do you have MetroWalk size 42 black and price?"})(),
            run=run,
            system_prompt="system",
            history=[],
            strategy_snapshot={},
            memory_snapshot={},
            prepared=prepared,
        )

        self.assertEqual(reply, "Yes, MetroWalk is available at AED 239.00.")
        self.assertEqual(usage["total_tokens"], 18)
        self.assertEqual(fake_client.calls[0]["tools"], [])
        prompt_text = "\n".join(str(message["content"]) for message in fake_client.calls[0]["messages"])
        self.assertIn("Prepared reply context", prompt_text)
        self.assertIn("MetroWalk Office Loafer", prompt_text)
        self.assertEqual(run.model_name, "fake-composer")
        json.dumps(run.prompt_snapshot_json)

    def test_model_composer_retries_when_model_exposes_reasoning(self) -> None:
        fake_client = FakeChatClient(
            [
                "The context says the customer asked for price, so we should mention AED 239.00.",
                "MetroWalk Office Loafer in EU 42 / Black is available at AED 239.00. Would you like me to prepare a draft for staff review?",
            ]
        )
        service = CustomerCommunicationService(lambda: None, ai_client=fake_client)  # type: ignore[arg-type]

        reply, _ = service._compose_model_customer_reply(
            client=self._client(),
            playbook=self._playbook("shoe_store"),
            channel=type("Channel", (), {"provider": "website"})(),
            conversation=CustomerConversationModel(memory_json={}),
            inbound=type("Inbound", (), {"message_text": "Price for MetroWalk?"})(),
            run=AssistantRunModel(prompt_snapshot_json={}),
            system_prompt="system",
            history=[],
            strategy_snapshot={},
            memory_snapshot={},
            prepared=PreparedReplyContext(
                kind="catalog_grounded_answer",
                next_best_action="answer_grounded_fact_then_offer_one_next_step",
                facts={"selected_variant": {"label": "MetroWalk", "unit_price": {"display": "AED 239.00"}}},
                tool_names=("get_variant_price",),
            ),
        )

        self.assertEqual(len(fake_client.calls), 2)
        self.assertIn("MetroWalk Office Loafer", reply)
        self.assertFalse(service._contains_internal_reasoning(reply))

    def test_internal_reasoning_is_blocked_by_validator(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="How much is MetroWalk?",
            response_text="The context says the customer asked for price, so we should answer AED 239.",
            tool_names=["get_variant_price"],
            playbook=self._playbook("shoe_store"),
        )

        self.assertEqual(status, "escalated")
        self.assertIn("internal reasoning", reason)

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
        self.assertEqual(queries[0], "test2")

    def test_catalog_grounding_context_contains_tool_facts_not_customer_sentence(self) -> None:
        context = self.service._catalog_grounding_reply_context(
            self._client(),
            self._playbook("shoe_store"),
            CustomerConversationModel(memory_json={}),
            "Do you have MetroWalk in stock and what is the price?",
            CatalogGrounding(
                query="MetroWalk",
                tool_names=("search_catalog_variants", "get_variant_availability", "get_variant_price"),
                search_result={
                    "items": [
                        {
                            "variant_id": "variant-1",
                            "label": "MetroWalk Office Loafer / EU 42 / Black",
                            "sku": "MWL-42-BLK",
                            "available_to_sell": "3.000",
                            "unit_price": "239.00",
                        }
                    ]
                },
                availability_result={
                    "variant": {
                        "variant_id": "variant-1",
                        "label": "MetroWalk Office Loafer / EU 42 / Black",
                        "sku": "MWL-42-BLK",
                        "available_to_sell": "3.000",
                        "unit_price": "239.00",
                    }
                },
                price_result={
                    "variant": {
                        "variant_id": "variant-1",
                        "label": "MetroWalk Office Loafer / EU 42 / Black",
                        "sku": "MWL-42-BLK",
                        "unit_price": "239.00",
                    }
                },
            ),
        )

        self.assertEqual(context["match_status"], "single_available_match")
        self.assertEqual(context["selected_variant"]["sku"], "MWL-42-BLK")
        self.assertEqual(context["selected_variant"]["unit_price"]["display"], "AED 239.00")
        self.assertEqual(context["selected_variant"]["available_to_sell"], "3")

    def test_catalog_grounding_context_handles_multiple_matches_as_options(self) -> None:
        conversation = CustomerConversationModel(memory_json={})
        context = self.service._catalog_grounding_reply_context(
            self._client(),
            self._playbook("shoe_store"),
            conversation,
            "Show me black office shoes",
            CatalogGrounding(
                query="black office shoes",
                tool_names=("search_catalog_variants",),
                search_result={
                    "items": [
                        {"variant_id": "1", "label": "MetroWalk / 42 / Black", "sku": "MWL", "available_to_sell": "3.000", "unit_price": "239.00"},
                        {"variant_id": "2", "label": "CloudStep / 42 / Black", "sku": "CSD", "available_to_sell": "5.000", "unit_price": "289.00"},
                    ]
                },
            ),
        )

        self.assertEqual(context["match_status"], "multiple_close_matches")
        self.assertEqual(len(context["choices"]), 2)
        self.assertEqual(conversation.memory_json["recent_choices"][0]["sku"], "MWL")

    def test_policy_facts_use_structured_playbook_policy(self) -> None:
        playbook = self._playbook("fashion")
        playbook.policy_json = {"returns": "Exchange or return within 7 days if unused and tags are attached."}

        facts = self.service._policy_facts_for_message(playbook, "Can I return it if it does not fit?")

        self.assertEqual(facts["requested_policy_keys"], ["returns"])
        self.assertEqual(facts["known_policies"]["returns"], "Exchange or return within 7 days if unused and tags are attached.")
        self.assertFalse(facts["staff_confirmation_required"])

    def test_unknown_policy_is_marked_for_staff_confirmation(self) -> None:
        facts = self.service._policy_facts_for_message(self._playbook("shoe_store"), "What is your warranty?")

        self.assertEqual(facts["unknown_policy_keys"], ["warranty"])
        self.assertTrue(facts["staff_confirmation_required"])

    def test_discovery_context_uses_template_questions_and_memory(self) -> None:
        conversation = CustomerConversationModel(memory_json={"preferences": {"size": "42"}})
        context = self.service._discovery_reply_context(
            playbook=self._playbook("shoe_store"),
            conversation=conversation,
            inbound_text="Can you recommend shoes for work?",
        )

        self.assertEqual(context["known_preferences"], {"size": "42"})
        self.assertIn("shoe size", context["preference_questions"])
        self.assertIn("budget", context["missing_preference_questions"])

    def test_banglish_budget_shoe_request_updates_language_and_buyer_type(self) -> None:
        conversation = CustomerConversationModel(memory_json={"buyer_archetype": "explorer"})
        playbook = self._playbook("shoe_store")
        inbound = "Ami je kono formal shoe khujtesi. but within budget"

        self.service._remember_inbound_context(conversation, playbook, inbound)
        snapshot = self.service._conversation_strategy_snapshot(conversation, inbound)

        self.assertEqual((conversation.memory_json or {})["language_hint"], "bengali")
        self.assertEqual(snapshot["customer_signals"]["buyer_archetype"], "budget_buyer")

    def test_better_price_uses_recent_recommendation_for_fresh_grounding(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "recent_choices": [
                    {
                        "variant_id": "variant-1",
                        "label": "CloudStep Daily Sneaker / EU 42 / Black",
                        "sku": "CSD-42-BLK",
                    }
                ]
            }
        )

        remembered = self.service._remembered_variant_for_message(
            conversation,
            "Can you do better price? I might order today if it makes sense.",
        )

        self.assertIsNotNone(remembered)
        self.assertEqual(remembered["variant_id"], "variant-1")

    def test_price_negotiation_does_not_jump_to_draft_order_collection(self) -> None:
        result = self.service._draft_order_reply_context(
            None,  # type: ignore[arg-type]
            client=self._client(),
            channel=object(),  # type: ignore[arg-type]
            conversation=CustomerConversationModel(memory_json={}),
            inbound=type("Inbound", (), {"message_text": "Can you do better price? I might order today if it makes sense."})(),
            run=object(),  # type: ignore[arg-type]
            grounding=CatalogGrounding(
                query="CSD-42-BLK",
                tool_names=("search_catalog_variants",),
                search_result={
                    "items": [
                        {
                            "variant_id": "variant-1",
                            "label": "CloudStep Daily Sneaker / EU 42 / Black",
                            "available_to_sell": "5.000",
                        }
                    ]
                },
            ),
        )

        self.assertIsNone(result)

    def test_draft_order_context_collects_contact_and_preserves_requested_price(self) -> None:
        conversation = CustomerConversationModel(memory_json={})
        context = self.service._draft_order_reply_context(
            None,  # type: ignore[arg-type]
            client=self._client(),
            channel=object(),  # type: ignore[arg-type]
            conversation=conversation,
            inbound=type("Inbound", (), {"message_text": "Can you do AED 220? I will order now."})(),
            run=object(),  # type: ignore[arg-type]
            grounding=CatalogGrounding(
                query="MWL",
                tool_names=("search_catalog_variants", "get_variant_availability"),
                search_result={
                    "items": [
                        {
                            "variant_id": "variant-1",
                            "label": "MetroWalk Office Loafer / EU 42 / Black",
                            "sku": "MWL-42-BLK",
                            "available_to_sell": "3.000",
                        }
                    ]
                },
                availability_result={
                    "variant": {
                        "variant_id": "variant-1",
                        "label": "MetroWalk Office Loafer / EU 42 / Black",
                        "sku": "MWL-42-BLK",
                        "available_to_sell": "3.000",
                    }
                },
            ),
        )

        self.assertIsNotNone(context)
        self.assertEqual(context["kind"], "draft_order_contact_needed")
        self.assertEqual(context["requested_price"]["display"], "AED 220.00")
        self.assertEqual(conversation.memory_json["sales_state"]["requested_price"], "220")

    def test_requested_price_extraction_requires_price_context(self) -> None:
        self.assertEqual(self.service._extract_requested_price("Can you do AED 220 if I order now?"), Decimal("220"))
        self.assertIsNone(self.service._extract_requested_price("Prepare draft order for MetroWalk size 42 black."))

    def test_draft_status_context_marks_order_not_confirmed(self) -> None:
        conversation = CustomerConversationModel(
            draft_order_id="order-1",
            memory_json={
                "sales_state": {
                    "focus_label": "MetroWalk Office Loafer / EU 42 / Black",
                    "draft_order": {"order_number": "SO-123"},
                },
            },
        )

        context = self.service._sales_progress_context(
            client=self._client(),
            conversation=conversation,
            inbound_text="Is my order confirmed now?",
        )

        self.assertEqual(context["kind"], "draft_order_status")
        self.assertEqual(context["draft_order"]["order_number"], "SO-123")
        self.assertTrue(context["order_status_guardrail"]["not_confirmed"])
        self.assertTrue(context["order_status_guardrail"]["not_charged"])

    def test_order_status_without_current_draft_does_not_use_related_memory(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "thread_graph": {"related_conversations": [{"latest_summary": "Assistant: draft order SO-OLD was prepared"}]},
            }
        )

        context = self.service._sales_progress_context(
            client=self._client(),
            conversation=conversation,
            inbound_text="Is my order confirmed now?",
        )

        self.assertEqual(context["kind"], "order_status_unknown_current_chat")
        self.assertFalse(context["order_status_guardrail"]["current_chat_has_draft_order"])
        self.assertTrue(context["order_status_guardrail"]["do_not_use_related_conversation_as_current_order"])

    def test_draft_status_reply_does_not_need_fresh_order_tool(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="Is my order confirmed now?",
            response_text=(
                "Not confirmed yet. SO-123 is prepared as a draft for MetroWalk. "
                "The store team still needs to review final price, payment, and delivery before anything is confirmed, charged, or fulfilled."
            ),
            tool_names=[],
            playbook=self._playbook("shoe_store"),
        )

        self.assertEqual(status, "ok")
        self.assertEqual(reason, "")

    def test_unknown_order_status_reply_does_not_need_fresh_order_tool(self) -> None:
        status, reason = self.service._validate_response(
            inbound_text="Is my order confirmed now?",
            response_text="I do not see a current draft order in this chat yet. Send the order number or phone and the team can check it.",
            tool_names=[],
            playbook=self._playbook("shoe_store"),
        )

        self.assertEqual(status, "ok")
        self.assertEqual(reason, "")

    def test_negotiation_context_uses_discount_policy_without_promising(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "sales_state": {"focus_label": "Trail Runner / M / Black", "last_offered_price": "79.00"},
                "buyer_archetype": "budget_buyer",
            }
        )
        playbook = self._playbook("shoe_store")
        playbook.policy_json = {"discounts": "Discounts are staff-approved only."}

        context = self.service._negotiation_context(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=playbook,
            conversation=conversation,
            inbound_text="What is your best price?",
        )

        self.assertEqual(context["kind"], "price_negotiation")
        self.assertEqual(context["current_price"]["display"], "$79.00")
        self.assertEqual(context["discount_policy"], "Discounts are staff-approved only.")
        self.assertTrue(context["staff_review_required_for_discount"])

    def test_negotiation_context_handles_expensive_signal(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "sales_state": {"focus_label": "Trail Runner / M / Black"},
                "buyer_archetype": "campaign_buyer",
            }
        )

        context = self.service._negotiation_context(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=self._playbook("shoe_store"),
            conversation=conversation,
            inbound_text="Looks expensive for me.",
        )

        self.assertEqual(context["kind"], "price_objection")
        self.assertEqual(context["focus_label"], "Trail Runner / M / Black")
        self.assertIn("show lower-price alternative", context["allowed_moves"])

    def test_negotiation_context_supports_bundle_interest(self) -> None:
        conversation = CustomerConversationModel(memory_json={"sales_state": {"focus_label": "Trail Runner / M / Black"}})
        playbook = self._playbook("shoe_store")
        playbook.sales_goals_json = {"cross_sell": True}

        context = self.service._negotiation_context(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            playbook=playbook,
            conversation=conversation,
            inbound_text="Any socks or care kit to go with it?",
        )

        self.assertEqual(context["kind"], "bundle_interest")
        self.assertEqual(context["bundle_categories"], ["socks", "care items", "insoles"])

    def test_sales_progress_context_compares_recent_choices(self) -> None:
        conversation = CustomerConversationModel(
            memory_json={
                "preferences": {"size": "42", "occasion": "work", "budget": "250"},
                "recent_choices": [
                    {"label": "Ariya Soft Blazer / 42 / Black", "sku": "ASB-42-BLK", "unit_price": "219.00", "available_to_sell": "11.000"},
                    {"label": "City Oxford Knit / 42 / Black", "sku": "COK-42-BLK", "unit_price": "199.00", "available_to_sell": "8.000"},
                ],
            }
        )

        context = self.service._sales_progress_context(
            client=self._client(),
            conversation=conversation,
            inbound_text="Which one is better?",
        )

        self.assertEqual(context["kind"], "comparison")
        self.assertEqual(context["preferred_choice"]["sku"], "ASB-42-BLK")
        self.assertEqual(len(context["recent_choices"]), 2)

    def test_sales_progress_context_updates_hesitation_memory(self) -> None:
        conversation = CustomerConversationModel(memory_json={"sales_state": {"focus_label": "Trail Runner / M / Black"}})

        context = self.service._sales_progress_context(
            client=type("Client", (), {"currency_symbol": "$", "currency_code": "USD"})(),
            conversation=conversation,
            inbound_text="Maybe later, I will think about it.",
        )

        self.assertEqual(context["kind"], "customer_hesitation")
        self.assertEqual(conversation.memory_json["negotiation_state"]["stall_count"], 1)
        self.assertEqual(conversation.memory_json["negotiation_state"]["last_move"], "hesitation_soft_hold")

    def test_media_context_asks_for_focus_detail_without_fake_vision(self) -> None:
        conversation = CustomerConversationModel(memory_json={"message_modality": {"has_image": True}})

        context = self.service._media_reply_context(
            conversation=conversation,
            inbound_text="See attached screenshot, what do you think?",
        )

        self.assertFalse(context["vision_available"])
        self.assertIn("product name", context["needed_details"])

    def test_language_instruction_uses_stored_language_hint(self) -> None:
        conversation = CustomerConversationModel(memory_json={"language_hint": "arabic"})
        self.assertIn("Reply in Arabic", self.service._language_instruction(conversation))

    def test_language_hint_detects_arabic_text(self) -> None:
        self.assertEqual(self.service._detect_language_hint("مرحبا، أريد حذاء أسود"), "arabic")

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

    def test_browse_language_triggers_catalog_grounding_without_price_words(self) -> None:
        queries = self.service._catalog_search_queries("What is formal shoe collection?")

        self.assertTrue(self.service._needs_catalog_grounding("What is formal shoe collection?"))
        self.assertEqual(queries[0], "formal shoe")


if __name__ == "__main__":
    unittest.main()
