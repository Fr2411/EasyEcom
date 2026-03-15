from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password, hash_token
from easy_ecom.data.store.postgres_models import (
    AuditLogModel,
    CategoryModel,
    ChannelConversationModel,
    ChannelIntegrationModel,
    ChannelMessageModel,
    ChannelMessageProductMentionModel,
    ClientSettingsModel,
    InventoryLedgerModel,
    LocationModel,
    ProductModel,
    ProductVariantModel,
    SupplierModel,
    TenantAgentProfileModel,
)
from easy_ecom.domain.services.sales_agent_service import SalesAgentService
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user


CLIENT_ID = "22222222-2222-2222-2222-222222222222"
LOCATION_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_CLIENT_ID = "44444444-4444-4444-4444-444444444444"
OTHER_USER_ID = "55555555-5555-5555-5555-555555555555"


def _setup_runtime(tmp_path: Path, monkeypatch):
    runtime = build_sqlite_runtime(tmp_path, "sales_agent.db")
    monkeypatch.setattr(deps, "settings", runtime.settings)
    seed_auth_user(
        runtime.session_factory,
        user_id=USER_ID,
        client_id=CLIENT_ID,
        email="owner@example.com",
        name="Owner",
        password_hash=hash_password("secret"),
        role_code="CLIENT_OWNER",
    )
    with runtime.session_factory() as session:
        if session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == CLIENT_ID)
        ).scalar_one_or_none() is None:
            session.add(
                ClientSettingsModel(
                    client_settings_id=new_uuid(),
                    client_id=CLIENT_ID,
                    low_stock_threshold=Decimal("2"),
                    allow_backorder=False,
                    default_location_name="Main Warehouse",
                    require_discount_approval=False,
                    order_prefix="SO",
                    purchase_prefix="PO",
                    return_prefix="RT",
                )
            )
        if session.execute(
            select(LocationModel).where(LocationModel.client_id == CLIENT_ID, LocationModel.location_id == LOCATION_ID)
        ).scalar_one_or_none() is None:
            session.add(
                LocationModel(
                    location_id=LOCATION_ID,
                    client_id=CLIENT_ID,
                    name="Main Warehouse",
                    code="MAIN",
                    is_default=True,
                    status="active",
                )
            )
        session.commit()
    return runtime


def _login_client() -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": "owner@example.com", "password": "secret"})
    assert response.status_code == 200
    return client


def _seed_variant(runtime, *, stock_qty: Decimal = Decimal("6")) -> dict[str, str]:
    with runtime.session_factory() as session:
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Default Supplier",
            code="SUP-SA",
            status="active",
        )
        category = CategoryModel(
            category_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Footwear",
            slug="footwear-sales-agent",
            status="active",
        )
        product = ProductModel(
            product_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            category_id=category.category_id,
            name="Trail Runner",
            slug="trail-runner-sales-agent",
            sku_root="TRAIL",
            brand="Easy Brand",
            description="Trail Runner description",
            status="active",
            default_price_amount=Decimal("75"),
            min_price_amount=Decimal("65"),
            max_discount_percent=Decimal("10"),
        )
        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=product.product_id,
            title="42 / Black",
            sku="TRAIL-42-BLACK",
            barcode="BC-TRAIL-42-BLACK",
            option_values_json={"size": "42", "color": "Black", "other": ""},
            status="active",
            cost_amount=Decimal("40"),
            price_amount=Decimal("75"),
            min_price_amount=Decimal("65"),
            reorder_level=Decimal("1"),
        )
        session.add_all([supplier, category])
        session.flush()
        session.add_all([product, variant])
        session.flush()
        session.add(
            InventoryLedgerModel(
                entry_id=new_uuid(),
                client_id=CLIENT_ID,
                variant_id=variant.variant_id,
                location_id=LOCATION_ID,
                movement_type="stock_received",
                reference_type="seed",
                reference_id=new_uuid(),
                reference_line_id=None,
                quantity_delta=stock_qty,
                unit_cost_amount=Decimal("40"),
                unit_price_amount=Decimal("75"),
                reason="Seed stock",
                created_by_user_id=USER_ID,
            )
        )
        session.commit()
        return {
            "product_id": str(product.product_id),
            "variant_id": str(variant.variant_id),
        }


def _upsert_integration(client: TestClient, **overrides: object) -> dict[str, object]:
    payload = {
        "display_name": "WhatsApp Sales Agent",
        "external_account_id": "waba-1",
        "phone_number_id": "phone-1",
        "phone_number": "+971551234567",
        "verify_token": "verify-me",
        "access_token": "",
        "app_secret": "",
        "default_location_id": LOCATION_ID,
        "auto_send_enabled": False,
        "agent_enabled": True,
        "model_name": "gpt-5-mini",
        "persona_prompt": "Sell honestly and stay grounded in stock and price truth.",
    }
    payload.update(overrides)
    response = client.put("/integrations/channels/whatsapp/meta", json=payload)
    assert response.status_code == 200
    return response.json()


def _webhook_payload(message_id: str, text: str, *, sender: str = "971551234567") -> dict[str, object]:
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "entry-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": "+971551234567",
                                "phone_number_id": "phone-1",
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Walker One"},
                                    "wa_id": sender,
                                }
                            ],
                            "messages": [
                                {
                                    "from": sender,
                                    "id": message_id,
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }


def _webhook_key(runtime) -> str:
    with runtime.session_factory() as session:
        integration = session.execute(
            select(ChannelIntegrationModel).where(ChannelIntegrationModel.client_id == CLIENT_ID)
        ).scalar_one()
        return str(integration.webhook_key)


def test_whatsapp_integration_can_be_saved_and_listed(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    empty_response = client.get("/integrations/channels")
    assert empty_response.status_code == 200
    assert empty_response.json()["items"] == []

    saved = _upsert_integration(
        client,
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    channel = saved["channel"]
    assert channel["provider"] == "whatsapp"
    assert channel["status"] == "active"
    assert channel["access_token_set"] is True
    assert channel["inbound_secret_set"] is True
    assert saved["setup_verify_token"] == "verify-me"

    listed = client.get("/integrations/channels")
    assert listed.status_code == 200
    items = listed.json()["items"]
    assert len(items) == 1
    assert items[0]["phone_number_id"] == "phone-1"

    with runtime.session_factory() as session:
        profile = session.execute(
            select(TenantAgentProfileModel).where(TenantAgentProfileModel.client_id == CLIENT_ID)
        ).scalar_one()
        assert str(profile.default_location_id) == LOCATION_ID
        assert profile.is_enabled is True


def test_public_webhook_verification_is_idempotent_and_persists_conversation(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime)
    client = _login_client()

    _upsert_integration(client, verify_token="verify-price")
    webhook_key = _webhook_key(runtime)

    verify_response = client.get(
        f"/public/webhooks/whatsapp/{webhook_key}",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-price",
            "hub.challenge": "challenge-123",
        },
    )
    assert verify_response.status_code == 200
    assert verify_response.text == "challenge-123"

    payload = _webhook_payload("wamid-price-1", "What is the price for Trail Runner 42 Black today?")
    first_response = client.post(f"/public/webhooks/whatsapp/{webhook_key}", json=payload)
    second_response = client.post(f"/public/webhooks/whatsapp/{webhook_key}", json=payload)
    assert first_response.status_code == 200
    assert first_response.json()["processed_messages"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["processed_messages"] == 0

    conversations_response = client.get("/sales-agent/conversations")
    assert conversations_response.status_code == 200
    conversations = conversations_response.json()["items"]
    assert len(conversations) == 1
    conversation = conversations[0]
    assert conversation["status"] == "needs_review"
    assert conversation["customer_type"] == "new"
    assert conversation["last_message_preview"].startswith("What is the price")
    assert "Trail Runner" in conversation["latest_recommended_products_summary"]

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["direction"] == "inbound"
    assert detail["messages"][0]["message_text"].startswith("What is the price")
    assert len(detail["messages"][0]["mentions"]) >= 1
    assert detail["latest_draft"]["status"] == "needs_review"

    with runtime.session_factory() as session:
        messages = session.execute(
            select(ChannelMessageModel).where(ChannelMessageModel.client_id == CLIENT_ID)
        ).scalars().all()
        mentions = session.execute(
            select(ChannelMessageProductMentionModel).where(ChannelMessageProductMentionModel.client_id == CLIENT_ID)
        ).scalars().all()
        audit_actions = {
            item.action
            for item in session.execute(
                select(AuditLogModel).where(AuditLogModel.client_id == CLIENT_ID)
            ).scalars()
        }
        assert len(messages) == 1
        assert len(mentions) >= 1
        assert "sales_agent_message_received" in audit_actions
        assert "sales_agent_draft_created" in audit_actions


def test_sales_agent_review_and_order_confirmation_flow(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime, stock_qty=Decimal("10"))
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-sent-1",
            "response": {"messages": [{"id": "wamid-sent-1"}]},
        },
    )

    _upsert_integration(client, verify_token="verify-order", access_token="meta-token")
    webhook_key = _webhook_key(runtime)

    inbound_response = client.post(
        f"/public/webhooks/whatsapp/{webhook_key}",
        json=_webhook_payload("wamid-order-1", "I want 2 Trail Runner 42 Black"),
    )
    assert inbound_response.status_code == 200
    assert inbound_response.json()["processed_messages"] == 1

    conversations_response = client.get("/sales-agent/conversations")
    conversation = conversations_response.json()["items"][0]
    assert conversation["linked_draft_order_id"] is not None
    assert conversation["latest_draft_id"] is not None

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    draft_id = detail["latest_draft"]["draft_id"]
    order_id = detail["linked_order"]["sales_order_id"]

    orders_response = client.get("/sales-agent/orders", params={"status": "draft"})
    assert orders_response.status_code == 200
    orders = orders_response.json()["items"]
    assert len(orders) == 1
    assert orders[0]["source_type"] == "sales_agent"
    assert orders[0]["source_conversation_id"] == conversation["conversation_id"]

    approve_response = client.post(
        f"/sales-agent/drafts/{draft_id}/approve-send",
        json={"edited_text": "Reserved for you. Confirm now and I will move this forward."},
    )
    assert approve_response.status_code == 200
    approved_draft = approve_response.json()
    assert approved_draft["status"] == "sent"
    assert approved_draft["human_modified"] is True
    assert approved_draft["final_text"].startswith("Reserved for you")

    confirm_response = client.post(f"/sales-agent/orders/{order_id}/confirm", json={})
    assert confirm_response.status_code == 200
    confirmed_order = confirm_response.json()["order"]
    assert confirmed_order["status"] == "confirmed"
    assert confirmed_order["source_type"] == "sales_agent"
    assert confirmed_order["source_agent_draft_id"] == draft_id

    refreshed_detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert refreshed_detail.status_code == 200
    assert refreshed_detail.json()["linked_order"]["status"] == "confirmed"

    with runtime.session_factory() as session:
        outbound_messages = session.execute(
            select(ChannelMessageModel).where(
                ChannelMessageModel.client_id == CLIENT_ID,
                ChannelMessageModel.direction == "outbound",
            )
        ).scalars().all()
        audit_actions = {
            item.action
            for item in session.execute(
                select(AuditLogModel).where(AuditLogModel.client_id == CLIENT_ID)
            ).scalars()
        }
        assert len(outbound_messages) == 1
        assert outbound_messages[0].provider_event_id == "wamid-sent-1"
        assert "sales_agent_order_created" in audit_actions
        assert "sales_agent_draft_sent" in audit_actions
        assert "sales_agent_order_confirmed" in audit_actions


def test_sales_agent_conversation_routes_are_tenant_scoped(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seed_auth_user(
        runtime.session_factory,
        user_id=OTHER_USER_ID,
        client_id=OTHER_CLIENT_ID,
        email="other-owner@example.com",
        name="Other Owner",
        password_hash=hash_password("secret"),
        role_code="CLIENT_OWNER",
    )
    client = _login_client()

    other_channel_id = new_uuid()
    other_conversation_id = new_uuid()
    with runtime.session_factory() as session:
        session.add(
            ChannelIntegrationModel(
                channel_id=other_channel_id,
                client_id=OTHER_CLIENT_ID,
                provider="whatsapp",
                display_name="Other Tenant WhatsApp",
                status="active",
                external_account_id="other-waba",
                phone_number_id="other-phone",
                phone_number="+15550001111",
                webhook_key="other-webhook",
                verify_token_hash=hash_token("other-verify"),
                access_token="other-token",
                app_secret="",
                auto_send_enabled=False,
                config_json={"model_name": "gpt-5-mini", "persona_prompt": "Other tenant"},
                created_by_user_id=OTHER_USER_ID,
            )
        )
        session.flush()
        session.add(
            ChannelConversationModel(
                conversation_id=other_conversation_id,
                client_id=OTHER_CLIENT_ID,
                channel_id=other_channel_id,
                customer_id=None,
                external_sender_id="15550002222",
                external_sender_phone="15550002222",
                customer_name_snapshot="Other Customer",
                customer_phone_snapshot="15550002222",
                customer_email_snapshot="",
                status="open",
                customer_type_snapshot="vip",
                behavior_tags_json=["price_sensitive"],
                latest_intent="pricing",
                latest_summary="Other summary",
                last_recommended_products_summary="Other products",
                last_message_preview="Other tenant conversation",
            )
        )
        session.commit()

    list_response = client.get("/sales-agent/conversations")
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []

    detail_response = client.get(f"/sales-agent/conversations/{other_conversation_id}")
    assert detail_response.status_code == 404

    integrations_response = client.get("/integrations/channels")
    assert integrations_response.status_code == 200
    assert integrations_response.json()["items"] == []
