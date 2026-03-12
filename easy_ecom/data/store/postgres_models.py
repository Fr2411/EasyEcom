from __future__ import annotations

from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from easy_ecom.data.store.postgres_db import Base


class ClientModel(Base):
    __tablename__ = "clients"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    business_name: Mapped[str] = mapped_column(String(255), default="")
    owner_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    currency_code: Mapped[str] = mapped_column(String(16), default="")
    currency_symbol: Mapped[str] = mapped_column(String(8), default="")
    website_url: Mapped[str] = mapped_column(String(255), default="")
    facebook_url: Mapped[str] = mapped_column(String(255), default="")
    instagram_url: Mapped[str] = mapped_column(String(255), default="")
    whatsapp_number: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(32), default="")
    notes: Mapped[str] = mapped_column(Text, default="")


class TenantSettingsModel(Base):
    __tablename__ = "tenant_settings"

    client_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    tax_registration_no: Mapped[str] = mapped_column(String(120), default="")
    low_stock_threshold: Mapped[str] = mapped_column(String(16), default="5")
    default_payment_terms_days: Mapped[str] = mapped_column(String(16), default="0")
    default_sales_note: Mapped[str] = mapped_column(Text, default="")
    default_inventory_adjustment_reasons: Mapped[str] = mapped_column(Text, default="")
    sales_prefix: Mapped[str] = mapped_column(String(12), default="SAL")
    returns_prefix: Mapped[str] = mapped_column(String(12), default="RET")
    purchases_prefix: Mapped[str] = mapped_column(String(12), default="PUR")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class UserModel(Base):
    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    password: Mapped[str] = mapped_column(Text, default="")
    password_hash: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class UserRoleModel(Base):
    __tablename__ = "user_roles"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    role_code: Mapped[str] = mapped_column(String(64), primary_key=True)


class CategoryModel(Base):
    __tablename__ = "categories"

    category_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")


class SupplierModel(Base):
    __tablename__ = "suppliers"

    supplier_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    contact_name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")


class CustomerModel(Base):
    __tablename__ = "customers"

    customer_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    full_name: Mapped[str] = mapped_column(String(255), index=True)
    phone: Mapped[str] = mapped_column(String(64), default="")
    email: Mapped[str] = mapped_column(String(255), default="")
    whatsapp: Mapped[str] = mapped_column(String(64), default="")
    address_line1: Mapped[str] = mapped_column(String(255), default="")
    address_line2: Mapped[str] = mapped_column(String(255), default="")
    area: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(128), default="")
    state: Mapped[str] = mapped_column(String(128), default="")
    postal_code: Mapped[str] = mapped_column(String(32), default="")
    country: Mapped[str] = mapped_column(String(128), default="")
    preferred_contact_channel: Mapped[str] = mapped_column(String(32), default="phone")
    marketing_opt_in: Mapped[str] = mapped_column(String(8), default="false")
    tags: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")


class ProductModel(Base):
    __tablename__ = "products"

    product_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    supplier: Mapped[str] = mapped_column(String(255), default="")
    product_name: Mapped[str] = mapped_column(String(255), index=True)
    category: Mapped[str] = mapped_column(String(255), default="")
    prd_description: Mapped[str] = mapped_column(Text, default="")
    prd_features_json: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    is_parent: Mapped[str] = mapped_column(String(8), default="true")
    sizes_csv: Mapped[str] = mapped_column(Text, default="")
    colors_csv: Mapped[str] = mapped_column(Text, default="")
    others_csv: Mapped[str] = mapped_column(Text, default="")
    parent_product_id: Mapped[str] = mapped_column(String(64), default="")


class ProductVariantModel(Base):
    __tablename__ = "product_variants"

    variant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    parent_product_id: Mapped[str] = mapped_column(String(64), index=True)
    variant_name: Mapped[str] = mapped_column(String(255), default="")
    size: Mapped[str] = mapped_column(String(64), default="")
    color: Mapped[str] = mapped_column(String(64), default="")
    other: Mapped[str] = mapped_column(String(64), default="")
    sku_code: Mapped[str] = mapped_column(String(128), default="")
    barcode: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[str] = mapped_column(String(8), default="true")
    created_at: Mapped[str] = mapped_column(String(64), default="")


class InventoryTxnModel(Base):
    __tablename__ = "inventory_txn"

    txn_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[str] = mapped_column(String(64), default="")
    user_id: Mapped[str] = mapped_column(String(64), default="")
    txn_type: Mapped[str] = mapped_column(String(32), default="")
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    variant_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    product_name: Mapped[str] = mapped_column(String(255), default="")
    qty: Mapped[str] = mapped_column(String(64), default="0")
    unit_cost: Mapped[str] = mapped_column(String(64), default="0")
    total_cost: Mapped[str] = mapped_column(String(64), default="0")
    supplier_snapshot: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="")
    source_id: Mapped[str] = mapped_column(String(64), default="")
    lot_id: Mapped[str] = mapped_column(String(64), default="")


class SalesOrderModel(Base):
    __tablename__ = "sales_orders"

    order_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    sale_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    timestamp: Mapped[str] = mapped_column(String(64), default="")
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default="confirmed")
    subtotal: Mapped[str] = mapped_column(String(64), default="0")
    discount: Mapped[str] = mapped_column(String(64), default="0")
    tax: Mapped[str] = mapped_column(String(64), default="0")
    grand_total: Mapped[str] = mapped_column(String(64), default="0")
    amount_paid: Mapped[str] = mapped_column(String(64), default="0")
    outstanding_balance: Mapped[str] = mapped_column(String(64), default="0")
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")


class SalesOrderItemModel(Base):
    __tablename__ = "sales_order_items"

    order_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    variant_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    product_name_snapshot: Mapped[str] = mapped_column(String(255), default="")
    qty: Mapped[str] = mapped_column(String(64), default="0")
    unit_selling_price: Mapped[str] = mapped_column(String(64), default="0")
    total_selling_price: Mapped[str] = mapped_column(String(64), default="0")


class FinanceExpenseModel(Base):
    __tablename__ = "finance_expenses"

    expense_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    expense_date: Mapped[str] = mapped_column(String(32), index=True, default="")
    category: Mapped[str] = mapped_column(String(120), index=True, default="")
    amount: Mapped[str] = mapped_column(String(64), default="0")
    payment_status: Mapped[str] = mapped_column(String(32), default="paid")
    note: Mapped[str] = mapped_column(Text, default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class SalesReturnModel(Base):
    __tablename__ = "sales_returns"

    return_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    return_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    sale_id: Mapped[str] = mapped_column(String(64), index=True)
    sale_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    customer_id: Mapped[str] = mapped_column(String(64), index=True)
    reason: Mapped[str] = mapped_column(String(255), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    return_total: Mapped[str] = mapped_column(String(64), default="0")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")


class SalesReturnItemModel(Base):
    __tablename__ = "sales_return_items"

    return_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    return_id: Mapped[str] = mapped_column(String(64), index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    sale_item_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    variant_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    product_name_snapshot: Mapped[str] = mapped_column(String(255), default="")
    sold_qty: Mapped[str] = mapped_column(String(64), default="0")
    return_qty: Mapped[str] = mapped_column(String(64), default="0")
    unit_price: Mapped[str] = mapped_column(String(64), default="0")
    line_total: Mapped[str] = mapped_column(String(64), default="0")
    reason: Mapped[str] = mapped_column(String(255), default="")
    condition_status: Mapped[str] = mapped_column(String(64), default="")


class PurchaseModel(Base):
    __tablename__ = "purchases"

    purchase_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    purchase_no: Mapped[str] = mapped_column(String(64), index=True, default="")
    purchase_date: Mapped[str] = mapped_column(String(32), index=True, default="")
    supplier_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    supplier_name_snapshot: Mapped[str] = mapped_column(String(255), default="")
    reference_no: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(32), default="received")
    subtotal: Mapped[str] = mapped_column(String(64), default="0")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")


class PurchaseItemModel(Base):
    __tablename__ = "purchase_items"

    purchase_item_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    purchase_id: Mapped[str] = mapped_column(String(64), index=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    product_id: Mapped[str] = mapped_column(String(64), index=True)
    variant_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    product_name_snapshot: Mapped[str] = mapped_column(String(255), default="")
    qty: Mapped[str] = mapped_column(String(64), default="0")
    unit_cost: Mapped[str] = mapped_column(String(64), default="0")
    line_total: Mapped[str] = mapped_column(String(64), default="0")


class ImportRunModel(Base):
    __tablename__ = "import_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    entity_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), index=True, nullable=False, default="running")
    total_rows: Mapped[str] = mapped_column(String(32), default="0")
    inserted_rows: Mapped[str] = mapped_column(String(32), default="0")
    updated_rows: Mapped[str] = mapped_column(String(32), default="0")
    skipped_rows: Mapped[str] = mapped_column(String(32), default="0")
    failed_rows: Mapped[str] = mapped_column(String(32), default="0")
    notes: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[str] = mapped_column(String(64), default="")
    finished_at: Mapped[str] = mapped_column(String(64), default="")


class ImportErrorModel(Base):
    __tablename__ = "import_errors"

    error_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    import_run_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    row_number: Mapped[str] = mapped_column(String(32), default="")
    raw_data: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(64), default="")


class ChannelIntegrationModel(Base):
    __tablename__ = "channel_integrations"

    channel_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True, default="webhook")
    display_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="inactive")
    external_account_id: Mapped[str] = mapped_column(String(255), default="")
    verify_token: Mapped[str] = mapped_column(String(255), default="")
    inbound_secret: Mapped[str] = mapped_column(String(255), default="")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    last_inbound_at: Mapped[str] = mapped_column(String(64), default="")


class ChannelConversationModel(Base):
    __tablename__ = "channel_conversations"

    conversation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    channel_id: Mapped[str] = mapped_column(String(64), index=True)
    external_sender_id: Mapped[str] = mapped_column(String(255), index=True, default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="open")
    customer_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    linked_sale_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    last_message_at: Mapped[str] = mapped_column(String(64), default="")


class ChannelMessageModel(Base):
    __tablename__ = "channel_messages"

    message_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    channel_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    direction: Mapped[str] = mapped_column(String(16), index=True, default="inbound")
    provider_event_id: Mapped[str] = mapped_column(String(255), index=True, default="")
    external_sender_id: Mapped[str] = mapped_column(String(255), index=True, default="")
    message_text: Mapped[str] = mapped_column(Text, default="")
    content_summary: Mapped[str] = mapped_column(String(280), default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    occurred_at: Mapped[str] = mapped_column(String(64), index=True, default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    outbound_status: Mapped[str] = mapped_column(String(32), default="prepared")
    created_by_user_id: Mapped[str] = mapped_column(String(64), default="")


class AiReviewDraftModel(Base):
    __tablename__ = "ai_review_drafts"

    draft_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    inbound_message_id: Mapped[str] = mapped_column(String(64), index=True)
    ai_draft_text: Mapped[str] = mapped_column(Text, default="")
    edited_text: Mapped[str] = mapped_column(Text, default="")
    final_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), index=True, default="draft_created")
    intent: Mapped[str] = mapped_column(String(64), default="")
    confidence: Mapped[str] = mapped_column(String(32), default="")
    grounding_json: Mapped[str] = mapped_column(Text, default="{}")
    requested_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    approved_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    sent_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
    approved_at: Mapped[str] = mapped_column(String(64), default="")
    sent_at: Mapped[str] = mapped_column(String(64), default="")
    failed_reason: Mapped[str] = mapped_column(Text, default="")
    send_result_json: Mapped[str] = mapped_column(Text, default="{}")


class TenantAutomationPolicyModel(Base):
    __tablename__ = "tenant_automation_policies"

    policy_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True, unique=True)
    automation_enabled: Mapped[str] = mapped_column(String(8), default="false")
    auto_send_enabled: Mapped[str] = mapped_column(String(8), default="false")
    emergency_disabled: Mapped[str] = mapped_column(String(8), default="false")
    categories_json: Mapped[str] = mapped_column(Text, default="{}")
    updated_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")


class AutomationDecisionModel(Base):
    __tablename__ = "automation_decisions"

    decision_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    client_id: Mapped[str] = mapped_column(String(64), index=True)
    conversation_id: Mapped[str] = mapped_column(String(64), index=True)
    inbound_message_id: Mapped[str] = mapped_column(String(64), index=True)
    policy_id: Mapped[str] = mapped_column(String(64), index=True)
    category: Mapped[str] = mapped_column(String(64), index=True, default="")
    classification_rule: Mapped[str] = mapped_column(String(120), default="")
    recommended_action: Mapped[str] = mapped_column(String(64), default="human_review")
    outcome: Mapped[str] = mapped_column(String(64), index=True, default="escalated")
    reason: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[str] = mapped_column(String(32), default="")
    candidate_reply: Mapped[str] = mapped_column(Text, default="")
    audit_context_json: Mapped[str] = mapped_column(Text, default="{}")
    run_by_user_id: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[str] = mapped_column(String(64), default="")
    updated_at: Mapped[str] = mapped_column(String(64), default="")
