from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from easy_ecom.api.dependencies import build_session_token
from easy_ecom.api import dependencies as deps
from easy_ecom.api.main import create_app
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.errors import ApiException
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
from easy_ecom.domain.models.auth import AuthenticatedUser
from easy_ecom.tests.support.sqlite_runtime import build_sqlite_runtime, seed_auth_user


CLIENT_ID = "22222222-2222-2222-2222-222222222222"
LOCATION_ID = "33333333-3333-3333-3333-333333333333"
USER_ID = "11111111-1111-1111-1111-111111111111"
OTHER_CLIENT_ID = "44444444-4444-4444-4444-444444444444"
OTHER_USER_ID = "55555555-5555-5555-5555-555555555555"
SUPER_ADMIN_ID = "66666666-6666-6666-6666-666666666666"
SUPER_ADMIN_CLIENT_ID = "77777777-7777-7777-7777-777777777777"


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


def _login(email: str, password: str) -> TestClient:
    client = TestClient(create_app())
    response = client.post("/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return client


def _seed_variant(
    runtime,
    *,
    stock_qty: Decimal = Decimal("6"),
    product_name: str = "Trail Runner",
    brand: str = "Easy Brand",
    title: str = "42 / Black",
    sku: str = "TRAIL-42-BLACK",
    barcode: str = "BC-TRAIL-42-BLACK",
    price_amount: Decimal = Decimal("75"),
    min_price_amount: Decimal = Decimal("65"),
) -> dict[str, str]:
    with runtime.session_factory() as session:
        suffix = new_uuid().split("-")[0]
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Default Supplier",
            code=f"SUP-{suffix}",
            status="active",
        )
        category = CategoryModel(
            category_id=new_uuid(),
            client_id=CLIENT_ID,
            name="Footwear",
            slug=f"footwear-sales-agent-{suffix}",
            status="active",
        )
        product = ProductModel(
            product_id=new_uuid(),
            client_id=CLIENT_ID,
            supplier_id=supplier.supplier_id,
            category_id=category.category_id,
            name=product_name,
            slug=f"sales-agent-{suffix}",
            sku_root=f"TRAIL-{suffix}",
            brand=brand,
            description=f"{product_name} description",
            status="active",
            default_price_amount=price_amount,
            min_price_amount=min_price_amount,
            max_discount_percent=Decimal("10"),
        )
        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=CLIENT_ID,
            product_id=product.product_id,
            title=title,
            sku=sku,
            barcode=barcode,
            option_values_json={"size": title.split("/")[0].strip(), "color": title.split("/")[-1].strip(), "other": ""},
            status="active",
            cost_amount=Decimal("40"),
            price_amount=price_amount,
            min_price_amount=min_price_amount,
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
                unit_price_amount=price_amount,
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
        "access_token": "meta-token",
        "app_secret": "meta-secret",
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


def _signed_webhook_request(client: TestClient, webhook_key: str, payload: dict[str, object], *, app_secret: str = "meta-secret"):
    raw_body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    signature = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return client.post(
        f"/public/webhooks/whatsapp/{webhook_key}",
        content=raw_body,
        headers={
            "content-type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )


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
    assert channel["config_saved"] is True
    assert channel["next_action"] == "Verify the callback URL in Meta with the exact verify token saved for this tenant."


def test_blank_secret_fields_preserve_existing_channel_credentials(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    _upsert_integration(client, verify_token="stable-verify", access_token="meta-token-1", app_secret="meta-secret-1")

    second_save = _upsert_integration(
        client,
        display_name="WhatsApp Sales Agent Updated",
        verify_token="",
        access_token="",
        app_secret="",
    )
    assert second_save["setup_verify_token"] is None
    assert second_save["channel"]["status"] == "active"
    assert second_save["channel"]["verify_token_set"] is True
    assert second_save["channel"]["access_token_set"] is True
    assert second_save["channel"]["inbound_secret_set"] is True

    with runtime.session_factory() as session:
        integration = session.execute(
            select(ChannelIntegrationModel).where(ChannelIntegrationModel.client_id == CLIENT_ID)
        ).scalar_one()
        assert integration.verify_token_hash == hash_token("stable-verify")
        assert integration.access_token == "meta-token-1"
        assert integration.app_secret == "meta-secret-1"
        assert integration.display_name == "WhatsApp Sales Agent Updated"


def test_whatsapp_integration_save_recovers_from_stale_session_user_id(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = TestClient(create_app())
    stale_user = AuthenticatedUser(
        user_id="legacy-user-id",
        client_id=CLIENT_ID,
        name="Owner",
        email="owner@example.com",
        business_name="EasyEcom Test",
        roles=["CLIENT_OWNER"],
        allowed_pages=["Dashboard", "Sales Agent", "Settings"],
    )
    client.cookies.set("easy_ecom_session", build_session_token(stale_user))

    response = client.put(
        "/integrations/channels/whatsapp/meta",
        json={
            "display_name": "WhatsApp Sales Agent",
            "external_account_id": "waba-1",
            "phone_number_id": "phone-1",
            "phone_number": "+971551234567",
            "verify_token": "verify-me",
            "access_token": "meta-token",
            "app_secret": "meta-secret",
            "default_location_id": LOCATION_ID,
            "auto_send_enabled": False,
            "agent_enabled": True,
            "model_name": "gpt-5-mini",
            "persona_prompt": "Sell honestly and stay grounded in stock and price truth.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["channel"]["provider"] == "whatsapp"

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


def test_super_admin_can_configure_tenant_integrations_by_client(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    seed_auth_user(
        runtime.session_factory,
        user_id=SUPER_ADMIN_ID,
        client_id=SUPER_ADMIN_CLIENT_ID,
        email="admin@example.com",
        name="Super Admin",
        password_hash=hash_password("secret"),
        role_code="SUPER_ADMIN",
    )
    client = _login("admin@example.com", "secret")

    locations_response = client.get("/integrations/channels/locations", params={"client_id": CLIENT_ID})
    assert locations_response.status_code == 200
    assert locations_response.json()["items"][0]["location_id"] == LOCATION_ID

    saved = client.put(
        "/integrations/channels/whatsapp/meta",
        params={"client_id": CLIENT_ID},
        json={
            "display_name": "Tenant WhatsApp",
            "external_account_id": "tenant-waba",
            "phone_number_id": "tenant-phone",
            "phone_number": "+971500000001",
            "verify_token": "tenant-verify",
            "access_token": "tenant-token",
            "app_secret": "tenant-secret",
            "default_location_id": LOCATION_ID,
            "auto_send_enabled": False,
            "agent_enabled": True,
            "model_name": "gpt-5-mini",
            "persona_prompt": "Sell for this tenant.",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["channel"]["phone_number_id"] == "tenant-phone"

    listed = client.get("/integrations/channels", params={"client_id": CLIENT_ID})
    assert listed.status_code == 200
    assert listed.json()["items"][0]["display_name"] == "Tenant WhatsApp"


def test_validate_run_diagnostics_and_send_smoke_surface_provider_state(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_probe_whatsapp_graph",
        lambda self, **kwargs: {
            "ok": True,
            "error_code": None,
            "error_message": None,
            "provider_status_code": 200,
            "provider_response_excerpt": None,
            "provider_details": {
                "display_phone_number": "+971551234567",
                "verified_name": "Test Number",
            },
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_probe_openai_model",
        lambda self, **kwargs: {
            "ok": False,
            "error_code": "openai_not_configured",
            "error_message": "OPENAI_API_KEY is not configured on the backend.",
            "provider_status_code": None,
            "provider_response_excerpt": None,
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-smoke-1",
            "response": {"messages": [{"id": "wamid-smoke-1"}]},
        },
    )

    validate_response = client.post(
        "/integrations/channels/whatsapp/meta/validate",
        json={
            "display_name": "WhatsApp Sales Agent",
            "external_account_id": "waba-1",
            "phone_number_id": "phone-1",
            "phone_number": "+971551234567",
            "verify_token": "verify-diagnostics",
            "access_token": "meta-token",
            "app_secret": "meta-secret",
            "default_location_id": LOCATION_ID,
            "auto_send_enabled": False,
            "agent_enabled": True,
            "model_name": "gpt-5-mini",
            "persona_prompt": "Sell honestly and stay grounded in stock and price truth.",
        },
    )
    assert validate_response.status_code == 200
    validate_payload = validate_response.json()
    assert validate_payload["diagnostics"]["config_saved"] is True
    assert validate_payload["diagnostics"]["graph_auth_ok"] is True
    assert validate_payload["diagnostics"]["openai_probe_ok"] is False
    assert validate_payload["provider_details"]["verified_name"] == "Test Number"

    saved = _upsert_integration(client, verify_token="verify-diagnostics")
    channel_id = saved["channel"]["channel_id"]

    validate_existing_response = client.post(
        "/integrations/channels/whatsapp/meta/validate",
        json={
            "display_name": "WhatsApp Sales Agent",
            "external_account_id": "waba-1",
            "phone_number_id": "phone-1",
            "phone_number": "+971551234567",
            "verify_token": "",
            "access_token": "",
            "app_secret": "",
            "default_location_id": LOCATION_ID,
            "auto_send_enabled": False,
            "agent_enabled": True,
            "model_name": "gpt-5-mini",
            "persona_prompt": "Sell honestly and stay grounded in stock and price truth.",
        },
    )
    assert validate_existing_response.status_code == 200
    assert validate_existing_response.json()["diagnostics"]["config_saved"] is True

    diagnostics_response = client.post(f"/integrations/channels/{channel_id}/run-diagnostics", json={})
    assert diagnostics_response.status_code == 200
    diagnostics_payload = diagnostics_response.json()
    assert diagnostics_payload["diagnostics"]["graph_auth_ok"] is True
    assert diagnostics_payload["diagnostics"]["last_error_code"] == "openai_not_configured"
    assert diagnostics_payload["channel"]["next_action"] == "Verify the callback URL in Meta with the exact verify token saved for this tenant."

    smoke_response = client.post(
        f"/integrations/channels/{channel_id}/send-smoke",
        json={"recipient": "+971500000001", "text": "Smoke test"},
    )
    assert smoke_response.status_code == 200
    smoke_payload = smoke_response.json()
    assert smoke_payload["ok"] is True
    assert smoke_payload["provider_event_id"] == "wamid-smoke-1"
    assert smoke_payload["diagnostics"]["outbound_send_ok"] is True

    with runtime.session_factory() as session:
        integration = session.execute(
            select(ChannelIntegrationModel).where(ChannelIntegrationModel.channel_id == channel_id)
        ).scalar_one()
        diagnostics = (integration.config_json or {}).get("diagnostics") or {}
        assert diagnostics["graph_auth_ok"] is True
        assert diagnostics["outbound_send_ok"] is True


def test_invalid_webhook_signature_is_rejected_and_recorded(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    _upsert_integration(client, verify_token="verify-signature", app_secret="meta-secret")
    webhook_key = _webhook_key(runtime)

    bad_response = client.post(
        f"/public/webhooks/whatsapp/{webhook_key}",
        content=json.dumps(_webhook_payload("wamid-bad-signature-1", "hello")).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "X-Hub-Signature-256": "sha256=bad-signature",
        },
    )
    assert bad_response.status_code == 401

    integrations_response = client.get("/integrations/channels")
    assert integrations_response.status_code == 200
    channel = integrations_response.json()["items"][0]
    assert channel["signature_validation_ok"] is False
    assert channel["last_error_code"] == "invalid_signature"
    assert channel["last_webhook_post_at"] is not None


def test_public_webhook_verification_is_idempotent_and_persists_conversation(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime)
    client = _login_client()

    _upsert_integration(client, verify_token="verify-price", app_secret="meta-secret")
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
    listed_after_verify = client.get("/integrations/channels")
    assert listed_after_verify.status_code == 200
    assert listed_after_verify.json()["items"][0]["webhook_verified_at"] is not None

    payload = _webhook_payload("wamid-price-1", "What is the price for Trail Runner 42 Black today?")
    first_response = _signed_webhook_request(client, webhook_key, payload)
    second_response = _signed_webhook_request(client, webhook_key, payload)
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

    integrations_response = client.get("/integrations/channels")
    assert integrations_response.status_code == 200
    channel = integrations_response.json()["items"][0]
    assert channel["last_webhook_post_at"] is not None
    assert channel["signature_validation_ok"] is True


def test_greeting_message_auto_sends_without_openai_or_product_match(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-greeting-1",
            "response": {"messages": [{"id": "wamid-greeting-1"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-greeting",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    inbound_response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-greeting-inbound-1", "hello"))
    assert inbound_response.status_code == 200
    assert inbound_response.json()["processed_messages"] == 1

    conversations_response = client.get("/sales-agent/conversations")
    assert conversations_response.status_code == 200
    conversation = conversations_response.json()["items"][0]
    assert conversation["status"] == "open"
    assert conversation["latest_draft_id"] is None
    assert conversation["last_message_preview"].lower().startswith("good to hear from you.")

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["messages"]) == 2
    assert detail["messages"][0]["direction"] == "inbound"
    assert detail["messages"][1]["direction"] == "outbound"
    assert "what are you" in detail["messages"][1]["message_text"].lower()
    assert "brand or style" not in detail["messages"][1]["message_text"].lower()
    assert detail["latest_draft"] is None


def test_duplicate_inbound_webhook_only_sends_one_auto_reply(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()
    outbound_texts: list[str] = []

    def _fake_send(self, integration, recipient, text):  # type: ignore[no-untyped-def]
        del self, integration, recipient
        outbound_texts.append(text)
        return {
            "provider": "whatsapp",
            "provider_event_id": f"wamid-greeting-dedup-{len(outbound_texts)}",
            "response": {"messages": [{"id": f"wamid-greeting-dedup-{len(outbound_texts)}"}]},
        }

    monkeypatch.setattr(SalesAgentService, "_send_whatsapp_text", _fake_send)

    _upsert_integration(
        client,
        verify_token="verify-greeting-dedup",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)
    payload = _webhook_payload("wamid-greeting-dedup-in-1", "hello")

    first_response = _signed_webhook_request(client, webhook_key, payload)
    second_response = _signed_webhook_request(client, webhook_key, payload)
    assert first_response.status_code == 200
    assert first_response.json()["processed_messages"] == 1
    assert second_response.status_code == 200
    assert second_response.json()["processed_messages"] == 0
    assert len(outbound_texts) == 1
    assert "what are you" in outbound_texts[0].lower()
    assert "brand or style" not in outbound_texts[0].lower()

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    assert len(detail["messages"]) == 2
    assert [item["direction"] for item in detail["messages"]] == ["inbound", "outbound"]


def test_follow_up_greeting_uses_shorter_non_repetitive_reply(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()
    outbound_texts: list[str] = []

    def _fake_send(self, integration, recipient, text):  # type: ignore[no-untyped-def]
        del self, integration, recipient
        outbound_texts.append(text)
        return {
            "provider": "whatsapp",
            "provider_event_id": f"wamid-greeting-followup-{len(outbound_texts)}",
            "response": {"messages": [{"id": f"wamid-greeting-followup-{len(outbound_texts)}"}]},
        }

    monkeypatch.setattr(SalesAgentService, "_send_whatsapp_text", _fake_send)

    _upsert_integration(
        client,
        verify_token="verify-greeting-followup",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    first_response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-greeting-followup-in-1", "hi"))
    second_response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-greeting-followup-in-2", "hello"))
    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.json()["processed_messages"] == 1
    assert second_response.json()["processed_messages"] == 1
    assert outbound_texts[0].startswith("Good to hear from you.")
    assert outbound_texts[1].startswith("I’m here.")
    assert outbound_texts[0] != outbound_texts[1]

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    assert len(detail["messages"]) == 4


def test_shop_name_query_returns_business_name_instead_of_product_match(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        brand="Adidas",
        title="40 / White",
        sku="CAMPUS-40-WHITE",
        barcode="BC-CAMPUS-40-WHITE",
        stock_qty=Decimal("11"),
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-business-info-1",
            "response": {"messages": [{"id": "wamid-business-info-1"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-business-info",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-business-info-in-1", "What's your shop name"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    assert len(detail["messages"]) == 2
    assert "client one" in detail["messages"][1]["message_text"].lower()
    assert "campus court low" not in detail["messages"][1]["message_text"].lower()
    assert detail["latest_trace"]["facts_pack"]["intent"] == "business_info"


def test_brand_list_query_uses_catalog_summary_instead_of_generic_clarifier(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        brand="Adidas",
        title="40 / Black",
        sku="ADI-CAMPUS-40-BLACK",
        barcode="BC-ADI-CAMPUS-40-BLACK",
        stock_qty=Decimal("8"),
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
    )
    _seed_variant(
        runtime,
        product_name="Air Swift",
        brand="Nike",
        title="41 / White",
        sku="NIKE-AIR-41-WHITE",
        barcode="BC-NIKE-AIR-41-WHITE",
        stock_qty=Decimal("6"),
        price_amount=Decimal("179"),
        min_price_amount=Decimal("159"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-brand-list-1",
            "response": {"messages": [{"id": "wamid-brand-list-1"}]},
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: kwargs["fallback"],
    )

    _upsert_integration(
        client,
        verify_token="verify-brand-list",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-brand-list-in-1", "What brands of shoes do you sell?"))
    assert response.status_code == 200

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    reply = detail["messages"][-1]["message_text"].lower()
    assert "adidas" in reply
    assert "nike" in reply
    assert "brand or style" not in reply
    assert detail["latest_trace"]["facts_pack"]["catalog_summary"]["top_brand_options"][:2] == ["Adidas", "Nike"]


def test_brand_only_correction_is_preserved_in_conversation_state(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        brand="Adidas",
        title="40 / Black",
        sku="ADI-CAMPUS-40-BLACK",
        barcode="BC-ADI-CAMPUS-40-BLACK",
        stock_qty=Decimal("8"),
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
    )
    _seed_variant(
        runtime,
        product_name="Street Runner",
        brand="Nike",
        title="40 / Black",
        sku="NIKE-STREET-40-BLACK",
        barcode="BC-NIKE-STREET-40-BLACK",
        stock_qty=Decimal("8"),
        price_amount=Decimal("159"),
        min_price_amount=Decimal("139"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "",
            "response": {"messages": [{"id": ""}]},
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: kwargs["fallback"],
    )

    _upsert_integration(
        client,
        verify_token="verify-correction",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    first = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-correction-1", "Do you have adidas"))
    second = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-correction-2", "Adidas only. Nothing else"))
    assert first.status_code == 200
    assert second.status_code == 200

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    state = detail["latest_trace"]["conversation_state_after"]
    assert "Adidas only" in state["customer_corrections"]
    assert state["active_brand"] == "Adidas"


def test_brand_query_prefers_brand_match_and_asks_for_size_or_style(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        brand="Adidas",
        title="40 / Black",
        sku="ADI-CAMPUS-40-BLACK",
        barcode="BC-ADI-CAMPUS-40-BLACK",
        stock_qty=Decimal("8"),
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
    )
    _seed_variant(
        runtime,
        product_name="Motion Lite Trainer",
        brand="Adidas",
        title="39 / Black",
        sku="ADI-MOTION-39-BLACK",
        barcode="BC-ADI-MOTION-39-BLACK",
        stock_qty=Decimal("6"),
        price_amount=Decimal("159"),
        min_price_amount=Decimal("139"),
    )
    _seed_variant(
        runtime,
        product_name="Little Steps School Shoe",
        brand="Easy Brand",
        title="30 / Black",
        sku="SCHOOL-30-BLACK",
        barcode="BC-SCHOOL-30-BLACK",
        stock_qty=Decimal("10"),
        price_amount=Decimal("55"),
        min_price_amount=Decimal("49"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-brand-query-1",
            "response": {"messages": [{"id": "wamid-brand-query-1"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-brand-query",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-brand-query-in-1", "I want adidas any black color shoe"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    reply = detail["messages"][1]["message_text"].lower()
    assert "adidas" in reply
    assert "range from" in reply
    assert "size or style" in reply
    assert "little steps" not in reply
    assert detail["latest_trace"]["runtime"]["helper_used"] is False
    assert detail["latest_trace"]["facts_pack"]["primary_matches"][0]["brand"] == "Adidas"


def test_running_shoe_context_carries_into_brand_follow_up_without_drifting(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Motion Lite Trainer",
        brand="Nike",
        title="39 / White",
        sku="NIKE-MOTION-39-WHITE",
        barcode="BC-NIKE-MOTION-39-WHITE",
        stock_qty=Decimal("9"),
        price_amount=Decimal("159"),
        min_price_amount=Decimal("139"),
    )
    _seed_variant(
        runtime,
        product_name="Atlas Runner",
        brand="Adidas",
        title="40 / Black",
        sku="ADI-ATLAS-40-BLACK",
        barcode="BC-ADI-ATLAS-40-BLACK",
        stock_qty=Decimal("8"),
        price_amount=Decimal("169"),
        min_price_amount=Decimal("149"),
    )
    _seed_variant(
        runtime,
        product_name="Ember Heel Sandal",
        brand="Easy Brand",
        title="37 / Black",
        sku="HEEL-37-BLACK",
        barcode="BC-HEEL-37-BLACK",
        stock_qty=Decimal("4"),
        price_amount=Decimal("129"),
        min_price_amount=Decimal("109"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "",
            "response": {"messages": [{"id": ""}]},
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: kwargs["fallback"],
    )

    _upsert_integration(
        client,
        verify_token="verify-running-context",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    first = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-running-context-1", "I'm interested in running shoes. Should be comfortable"))
    second = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-running-context-2", "I'm not worrying about the price but a good brand"))
    assert first.status_code == 200
    assert second.status_code == 200

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    reply = detail["messages"][-1]["message_text"].lower()
    assert "running shoes" in reply
    assert "ember heel sandal" not in reply
    assert "sandal" not in reply
    assert detail["latest_trace"]["facts_pack"]["active_constraints"]["active_need_label"] == "running shoes"
    labels = [item["label"].lower() for item in detail["latest_trace"]["facts_pack"]["primary_matches"]]
    assert any("runner" in label or "trainer" in label for label in labels)
    assert all("sandal" not in label and "heel" not in label for label in labels)


def test_formal_shoe_browse_with_known_size_asks_for_color_or_style_not_size(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Coast Loafer",
        brand="Classic Step",
        title="42 / Black",
        sku="LOAFER-42-BLACK",
        barcode="BC-LOAFER-42-BLACK",
        stock_qty=Decimal("4"),
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
    )
    _seed_variant(
        runtime,
        product_name="Coast Loafer",
        brand="Classic Step",
        title="42 / Brown",
        sku="LOAFER-42-BROWN",
        barcode="BC-LOAFER-42-BROWN",
        stock_qty=Decimal("3"),
        price_amount=Decimal("154"),
        min_price_amount=Decimal("129"),
    )
    _seed_variant(
        runtime,
        product_name="Motion Lite Trainer",
        brand="Adidas",
        title="42 / Black",
        sku="RUN-42-BLACK",
        barcode="BC-RUN-42-BLACK",
        stock_qty=Decimal("6"),
        price_amount=Decimal("159"),
        min_price_amount=Decimal("139"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "",
            "response": {"messages": [{"id": ""}]},
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: kwargs["fallback"],
    )

    _upsert_integration(
        client,
        verify_token="verify-formal",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)
    response = _signed_webhook_request(
        client,
        webhook_key,
        _webhook_payload("wamid-formal-1", "I wear size 42 and need some formal shoes."),
    )
    assert response.status_code == 200

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    reply = detail["messages"][-1]["message_text"].lower()
    assert "formal shoes" in reply
    assert "what size" not in reply
    assert "color or style" in reply
    assert detail["latest_trace"]["facts_pack"]["active_constraints"]["active_need_label"] == "formal shoes"


def test_accessories_query_without_catalog_match_answers_catalog_truth(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime, product_name="Trail Runner", brand="Adidas", title="42 / Black")
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "",
            "response": {"messages": [{"id": ""}]},
        },
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: kwargs["fallback"],
    )

    _upsert_integration(
        client,
        verify_token="verify-accessories",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)
    response = _signed_webhook_request(
        client,
        webhook_key,
        _webhook_payload("wamid-accessories-1", "I wanted to know what accessories you sell"),
    )
    assert response.status_code == 200

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    reply = detail["messages"][-1]["message_text"].lower()
    assert "not seeing accessories" in reply
    assert "shoes" in reply
    assert detail["latest_trace"]["facts_pack"]["active_constraints"]["active_need_label"] == "accessories"


def test_exact_variant_query_stays_deterministic_and_persists_offer_trace(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime, stock_qty=Decimal("8"))
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_helper_rank_candidates_with_model",
        lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("helper model should not run")),
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: (_ for _ in ()).throw(AssertionError("sales model should not run")),
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-tier0-1",
            "response": {"messages": [{"id": "wamid-tier0-1"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-tier0",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-tier0-in-1", "What is the price for Trail Runner 42 Black?"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1

    conversations = client.get("/sales-agent/conversations")
    assert conversations.status_code == 200
    conversation = conversations.json()["items"][0]
    assert conversation["status"] == "open"

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["messages"]) == 2
    assert detail["latest_draft"] is None
    assert detail["latest_trace"]["runtime"]["answer_type"] == "answer_and_ask"
    assert detail["latest_trace"]["runtime"]["sales_model_used"] is False
    assert detail["latest_trace"]["facts_pack"]["offer_policy"]["selected_offer_id"] == "list_price"
    assert detail["latest_trace"]["facts_pack"]["primary_matches"][0]["label"] == "Trail Runner / 42 / Black"
    assert "available at 75.00" in detail["messages"][1]["message_text"].lower()


def test_short_greeting_token_does_not_false_match_white_variant(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        title="40 / White",
        sku="CAMPUS-40-WHITE",
        barcode="BC-CAMPUS-40-WHITE",
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
        stock_qty=Decimal("11"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-greeting-2",
            "response": {"messages": [{"id": "wamid-greeting-2"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-greeting-short",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    inbound_response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-greeting-inbound-3", "hi"))
    assert inbound_response.status_code == 200
    assert inbound_response.json()["processed_messages"] == 1

    conversations_response = client.get("/sales-agent/conversations")
    assert conversations_response.status_code == 200
    conversation = conversations_response.json()["items"][0]
    assert conversation["status"] == "open"
    assert conversation["latest_recommended_products_summary"] == ""

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["messages"]) == 2
    assert "what are you" in detail["messages"][1]["message_text"].lower()
    assert "campus court low" not in detail["messages"][1]["message_text"].lower()


def test_ambiguous_query_stays_in_concierge_mode_without_helper(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        title="40 / White",
        sku="CAMPUS-40-WHITE",
        barcode="BC-CAMPUS-40-WHITE",
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
        stock_qty=Decimal("11"),
    )
    _seed_variant(
        runtime,
        product_name="Campus Court Low",
        title="40 / Black",
        sku="CAMPUS-40-BLACK",
        barcode="BC-CAMPUS-40-BLACK",
        price_amount=Decimal("149"),
        min_price_amount=Decimal("129"),
        stock_qty=Decimal("9"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_sales_reply_with_model",
        lambda self, **kwargs: kwargs["fallback"],
    )
    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-clarifier-1",
            "response": {"messages": [{"id": "wamid-clarifier-1"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-helper",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-helper-in-1", "Do you have Campus Court Low size 40?"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1

    detail = client.get("/sales-agent/conversations").json()["items"][0]
    detail_response = client.get(f"/sales-agent/conversations/{detail['conversation_id']}")
    assert detail_response.status_code == 200
    conversation_detail = detail_response.json()
    assert conversation_detail["latest_trace"]["runtime"]["helper_used"] is False
    assert conversation_detail["latest_trace"]["runtime"]["answer_type"] == "answer_and_ask"
    assert len(conversation_detail["latest_trace"]["facts_pack"]["primary_matches"]) == 2
    assert "which one should i price for you" in conversation_detail["messages"][1]["message_text"].lower()


def test_price_range_query_answers_first_then_asks_one_follow_up(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(
        runtime,
        product_name="Air Swift",
        brand="Nike",
        title="41 / Black",
        sku="NIKE-AIR-41-BLACK",
        barcode="BC-NIKE-AIR-41-BLACK",
        stock_qty=Decimal("5"),
        price_amount=Decimal("120"),
        min_price_amount=Decimal("110"),
    )
    _seed_variant(
        runtime,
        product_name="Street Runner",
        brand="Nike",
        title="42 / White",
        sku="NIKE-STREET-42-WHITE",
        barcode="BC-NIKE-STREET-42-WHITE",
        stock_qty=Decimal("7"),
        price_amount=Decimal("180"),
        min_price_amount=Decimal("165"),
    )
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: {
            "provider": "whatsapp",
            "provider_event_id": "wamid-range-1",
            "response": {"messages": [{"id": "wamid-range-1"}]},
        },
    )

    _upsert_integration(
        client,
        verify_token="verify-range",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-range-in-1", "I want to know the price range of Nike shoes"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    reply = detail["messages"][1]["message_text"].lower()
    assert "nike" in reply
    assert "120.00" in reply
    assert "180.00" in reply
    assert reply.count("?") <= 1
    assert detail["latest_trace"]["facts_pack"]["intent"] == "price_range"
    assert detail["latest_trace"]["facts_pack"]["range_summary"]["candidate_count"] == 2
    assert detail["latest_trace"]["facts_pack"]["active_constraints"]["active_brand"] == "Nike"


def test_inbound_message_is_saved_when_auto_send_fails(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    client = _login_client()

    monkeypatch.setattr(
        SalesAgentService,
        "_send_whatsapp_text",
        lambda self, integration, recipient, text: (_ for _ in ()).throw(
            ApiException(status_code=502, code="WHATSAPP_SEND_FAILED", message="Token expired")
        ),
    )

    _upsert_integration(
        client,
        verify_token="verify-send-fail",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    inbound_response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-greeting-inbound-2", "hello"))
    assert inbound_response.status_code == 200
    assert inbound_response.json()["processed_messages"] == 1

    conversations_response = client.get("/sales-agent/conversations")
    assert conversations_response.status_code == 200
    conversation = conversations_response.json()["items"][0]
    assert conversation["status"] == "needs_review"

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["direction"] == "inbound"
    assert detail["latest_draft"]["status"] == "needs_review"
    assert detail["latest_draft"]["failed_reason"] == "Token expired"
    assert "auto_send_failed" in detail["latest_draft"]["reason_codes"]


def test_review_mode_sends_acknowledgment_before_manual_follow_up(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime, stock_qty=Decimal("10"))
    client = _login_client()
    outbound_texts: list[str] = []

    def _fake_send(self, integration, recipient, text):  # type: ignore[no-untyped-def]
        del self, integration, recipient
        outbound_texts.append(text)
        return {
            "provider": "whatsapp",
            "provider_event_id": f"wamid-review-ack-{len(outbound_texts)}",
            "response": {"messages": [{"id": f"wamid-review-ack-{len(outbound_texts)}"}]},
        }

    monkeypatch.setattr(SalesAgentService, "_send_whatsapp_text", _fake_send)

    _upsert_integration(
        client,
        verify_token="verify-review-ack",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=False,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-review-ack-in-1", "Do you have Trail Runner 42 Black?"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1
    assert len(outbound_texts) == 1
    assert "checking" in outbound_texts[0].lower()

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    assert conversation["status"] == "needs_review"
    detail = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}").json()
    assert len(detail["messages"]) == 2
    assert detail["latest_draft"]["status"] == "needs_review"
    assert detail["latest_trace"]["runtime"]["review_ack_sent"] is True


def test_discount_request_respects_review_policy_and_offer_ladder(monkeypatch, tmp_path: Path) -> None:
    runtime = _setup_runtime(tmp_path, monkeypatch)
    _seed_variant(runtime, stock_qty=Decimal("12"))
    with runtime.session_factory() as session:
        settings_row = session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == CLIENT_ID)
        ).scalar_one()
        settings_row.require_discount_approval = True
        session.commit()
    client = _login_client()

    _upsert_integration(
        client,
        verify_token="verify-discount",
        access_token="meta-token",
        app_secret="meta-secret",
        auto_send_enabled=True,
    )
    webhook_key = _webhook_key(runtime)

    response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-discount-in-1", "Best discount for Trail Runner 42 Black?"))
    assert response.status_code == 200
    assert response.json()["processed_messages"] == 1

    conversation = client.get("/sales-agent/conversations").json()["items"][0]
    assert conversation["status"] == "needs_review"

    detail_response = client.get(f"/sales-agent/conversations/{conversation['conversation_id']}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["latest_draft"]["status"] == "needs_review"
    assert "discount_request" in detail["latest_draft"]["reason_codes"]
    offer_policy = detail["latest_draft"]["grounding"]["facts_pack"]["offer_policy"]
    assert offer_policy["requires_discount_approval"] is True
    assert offer_policy["selected_offer_id"] == "list_price"
    assert len(offer_policy["auto_discount_steps"]) >= 1


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

    inbound_response = _signed_webhook_request(client, webhook_key, _webhook_payload("wamid-order-1", "I want 2 Trail Runner 42 Black"))
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
        assert len(outbound_messages) == 2
        assert sorted(item.provider_event_id for item in outbound_messages) == ["", "wamid-sent-1"]
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
