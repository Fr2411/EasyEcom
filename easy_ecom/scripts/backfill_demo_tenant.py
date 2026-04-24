from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.slugs import slugify_identifier
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import (
    AssistantPlaybookModel,
    ClientModel,
    CustomerChannelModel,
    CustomerConversationModel,
    CustomerModel,
    InventoryLedgerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SupplierModel,
    UserModel,
)
from easy_ecom.domain.services.commerce_service import ZERO, as_decimal, normalize_email, normalize_phone
from easy_ecom.domain.services.customer_communication_service import DEFAULT_ESCALATION_RULES, INDUSTRY_TEMPLATES


DEMO_REFERENCE_ID = "DEMO-SHOE-STORE-20260424"
DEMO_CHANNEL_ACCOUNT_ID = "frabby-footwear-demo-website"


@dataclass(frozen=True)
class DemoVariant:
    title: str
    sku: str
    size: str
    color: str
    cost: Decimal
    price: Decimal
    target_stock: Decimal
    reorder_level: Decimal = Decimal("4")


@dataclass(frozen=True)
class DemoProduct:
    name: str
    sku_root: str
    brand: str
    category: str
    description: str
    variants: tuple[DemoVariant, ...]
    max_discount_percent: Decimal = Decimal("12")


DEMO_PRODUCTS: tuple[DemoProduct, ...] = (
    DemoProduct(
        name="AeroRun Flex Knit Running Shoe",
        sku_root="ARF",
        brand="AeroRun",
        category="Running Shoes",
        description="Lightweight breathable running shoe for daily runs and gym training.",
        variants=(
            DemoVariant("EU 40 / Black", "ARF-40-BLK", "40", "Black", Decimal("145"), Decimal("289"), Decimal("9")),
            DemoVariant("EU 41 / Black", "ARF-41-BLK", "41", "Black", Decimal("145"), Decimal("289"), Decimal("14")),
            DemoVariant("EU 42 / Black", "ARF-42-BLK", "42", "Black", Decimal("145"), Decimal("289"), Decimal("12")),
            DemoVariant("EU 43 / White", "ARF-43-WHT", "43", "White", Decimal("148"), Decimal("299"), Decimal("7")),
        ),
    ),
    DemoProduct(
        name="StrideMax Cushion Runner",
        sku_root="SMC",
        brand="StrideMax",
        category="Running Shoes",
        description="Soft-cushion running shoe for comfort-focused walkers and beginner runners.",
        variants=(
            DemoVariant("EU 41 / Navy", "SMC-41-NVY", "41", "Navy", Decimal("132"), Decimal("259"), Decimal("10")),
            DemoVariant("EU 42 / Navy", "SMC-42-NVY", "42", "Navy", Decimal("132"), Decimal("259"), Decimal("11")),
            DemoVariant("EU 43 / Grey", "SMC-43-GRY", "43", "Grey", Decimal("136"), Decimal("269"), Decimal("8")),
        ),
    ),
    DemoProduct(
        name="MetroCourt Leather Sneaker",
        sku_root="MCL",
        brand="MetroCourt",
        category="Lifestyle Sneakers",
        description="Minimal leather sneaker for smart casual outfits and everyday use.",
        variants=(
            DemoVariant("EU 40 / White", "MCL-40-WHT", "40", "White", Decimal("118"), Decimal("249"), Decimal("13")),
            DemoVariant("EU 41 / White", "MCL-41-WHT", "41", "White", Decimal("118"), Decimal("249"), Decimal("16")),
            DemoVariant("EU 42 / White", "MCL-42-WHT", "42", "White", Decimal("118"), Decimal("249"), Decimal("12")),
            DemoVariant("EU 42 / Black", "MCL-42-BLK", "42", "Black", Decimal("120"), Decimal("255"), Decimal("9")),
        ),
    ),
    DemoProduct(
        name="CloudStep Daily Sneaker",
        sku_root="CSD",
        brand="CloudStep",
        category="Lifestyle Sneakers",
        description="Flexible everyday sneaker with padded insole and clean casual styling.",
        variants=(
            DemoVariant("EU 39 / Beige", "CSD-39-BGE", "39", "Beige", Decimal("82"), Decimal("179"), Decimal("10")),
            DemoVariant("EU 40 / Beige", "CSD-40-BGE", "40", "Beige", Decimal("82"), Decimal("179"), Decimal("14")),
            DemoVariant("EU 41 / Black", "CSD-41-BLK", "41", "Black", Decimal("84"), Decimal("189"), Decimal("15")),
            DemoVariant("EU 42 / Black", "CSD-42-BLK", "42", "Black", Decimal("84"), Decimal("189"), Decimal("5")),
        ),
    ),
    DemoProduct(
        name="Oxford Prime Leather Formal Shoe",
        sku_root="OPL",
        brand="Oxford Prime",
        category="Formal Shoes",
        description="Polished leather Oxford for office, events, and formal wear.",
        variants=(
            DemoVariant("EU 41 / Black", "OPL-41-BLK", "41", "Black", Decimal("165"), Decimal("349"), Decimal("8")),
            DemoVariant("EU 42 / Black", "OPL-42-BLK", "42", "Black", Decimal("165"), Decimal("349"), Decimal("10")),
            DemoVariant("EU 43 / Brown", "OPL-43-BRN", "43", "Brown", Decimal("168"), Decimal("359"), Decimal("6")),
        ),
    ),
    DemoProduct(
        name="TrailGrip Outdoor Shoe",
        sku_root="TGO",
        brand="TrailGrip",
        category="Outdoor Shoes",
        description="Durable outdoor shoe with grippy sole for travel, light trails, and rainy days.",
        variants=(
            DemoVariant("EU 41 / Olive", "TGO-41-OLV", "41", "Olive", Decimal("152"), Decimal("319"), Decimal("7")),
            DemoVariant("EU 42 / Olive", "TGO-42-OLV", "42", "Olive", Decimal("152"), Decimal("319"), Decimal("9")),
            DemoVariant("EU 43 / Black", "TGO-43-BLK", "43", "Black", Decimal("155"), Decimal("329"), Decimal("6")),
        ),
    ),
    DemoProduct(
        name="FlexiStep Comfort Sandal",
        sku_root="FCS",
        brand="FlexiStep",
        category="Sandals",
        description="Comfort sandal for daily errands, travel, and relaxed weekend wear.",
        variants=(
            DemoVariant("EU 40 / Tan", "FCS-40-TAN", "40", "Tan", Decimal("54"), Decimal("129"), Decimal("12")),
            DemoVariant("EU 41 / Tan", "FCS-41-TAN", "41", "Tan", Decimal("54"), Decimal("129"), Decimal("15")),
            DemoVariant("EU 42 / Black", "FCS-42-BLK", "42", "Black", Decimal("56"), Decimal("139"), Decimal("11")),
        ),
    ),
    DemoProduct(
        name="LittleRunner Kids Sneaker",
        sku_root="LRS",
        brand="LittleRunner",
        category="Kids Shoes",
        description="Light kids sneaker with easy fastening and cushioned sole.",
        variants=(
            DemoVariant("EU 30 / Pink", "LRS-30-PNK", "30", "Pink", Decimal("48"), Decimal("109"), Decimal("10")),
            DemoVariant("EU 31 / Blue", "LRS-31-BLU", "31", "Blue", Decimal("48"), Decimal("109"), Decimal("8")),
            DemoVariant("EU 32 / Black", "LRS-32-BLK", "32", "Black", Decimal("50"), Decimal("119"), Decimal("9")),
        ),
    ),
    DemoProduct(
        name="Shoe Care Starter Kit",
        sku_root="SCK",
        brand="CareLab",
        category="Shoe Care",
        description="Cleaner, brush, and protector kit for sneakers and leather shoes.",
        variants=(DemoVariant("Standard Kit", "SCK-STD", "One size", "Mixed", Decimal("22"), Decimal("59"), Decimal("24")),),
        max_discount_percent=Decimal("18"),
    ),
    DemoProduct(
        name="Performance Cotton Socks 3 Pack",
        sku_root="PCS",
        brand="StrideMax",
        category="Accessories",
        description="Breathable cotton-rich socks for daily wear and sports shoes.",
        variants=(
            DemoVariant("M / White", "PCS-M-WHT", "M", "White", Decimal("12"), Decimal("39"), Decimal("30")),
            DemoVariant("L / Black", "PCS-L-BLK", "L", "Black", Decimal("12"), Decimal("39"), Decimal("26")),
        ),
        max_discount_percent=Decimal("20"),
    ),
)


DEMO_CUSTOMERS: tuple[dict[str, str], ...] = (
    {
        "code": "DEMO-CUS-MAYA",
        "name": "Maya Rahman",
        "email": "maya.demo@example.com",
        "phone": "+971501112233",
        "address": "Dubai Marina",
        "notes": "Demo customer interested in running shoes, usually size EU 41.",
    },
    {
        "code": "DEMO-CUS-OMAR",
        "name": "Omar Khan",
        "email": "omar.demo@example.com",
        "phone": "+971552223344",
        "address": "Business Bay",
        "notes": "Demo customer prefers formal leather shoes in black.",
    },
    {
        "code": "DEMO-CUS-SARA",
        "name": "Sara Ahmed",
        "email": "sara.demo@example.com",
        "phone": "+971563334455",
        "address": "Sharjah Al Majaz",
        "notes": "Demo customer buying kids shoes and accessories.",
    },
)


DEMO_ORDERS: tuple[dict[str, Any], ...] = (
    {
        "order_number": "SO-DEMO-SHOE-0001",
        "customer_code": "DEMO-CUS-MAYA",
        "days_ago": 10,
        "payment_status": "paid",
        "paid_amount": Decimal("328"),
        "lines": (("ARF-41-BLK", Decimal("1")), ("PCS-M-WHT", Decimal("1"))),
    },
    {
        "order_number": "SO-DEMO-SHOE-0002",
        "customer_code": "DEMO-CUS-OMAR",
        "days_ago": 6,
        "payment_status": "paid",
        "paid_amount": Decimal("349"),
        "lines": (("OPL-42-BLK", Decimal("1")),),
    },
    {
        "order_number": "SO-DEMO-SHOE-0003",
        "customer_code": "DEMO-CUS-SARA",
        "days_ago": 3,
        "payment_status": "partially_paid",
        "paid_amount": Decimal("120"),
        "lines": (("LRS-31-BLU", Decimal("1")), ("SCK-STD", Decimal("1"))),
    },
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _quantity(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))


def _tenant_user(session: Session, tenant_email: str) -> UserModel:
    user = session.execute(
        select(UserModel).where(func.lower(UserModel.email) == tenant_email.strip().lower())
    ).scalar_one_or_none()
    if user is None:
        raise RuntimeError(f"Tenant user not found for email: {tenant_email}")
    return user


def _default_location(session: Session, client_id: str) -> LocationModel:
    location = session.execute(
        select(LocationModel)
        .where(LocationModel.client_id == client_id, LocationModel.status == "active")
        .order_by(LocationModel.is_default.desc(), LocationModel.created_at.asc())
    ).scalars().first()
    if location is not None:
        location.name = "Frabby Footwear Showroom"
        location.code = location.code or "SHOWROOM"
        location.is_default = True
        return location

    location = LocationModel(
        location_id=new_uuid(),
        client_id=client_id,
        name="Frabby Footwear Showroom",
        code="SHOWROOM",
        is_default=True,
        status="active",
    )
    session.add(location)
    session.flush()
    return location


def _upsert_supplier(session: Session, client_id: str) -> SupplierModel:
    supplier = session.execute(
        select(SupplierModel).where(SupplierModel.client_id == client_id, SupplierModel.code == "DEMO-SHOE-SUP")
    ).scalar_one_or_none()
    if supplier is None:
        supplier = SupplierModel(
            supplier_id=new_uuid(),
            client_id=client_id,
            code="DEMO-SHOE-SUP",
            name="SoleBridge Wholesale",
        )
        session.add(supplier)
    supplier.name = "SoleBridge Wholesale"
    supplier.contact_name = "Demo Account Team"
    supplier.email = "supply@solebridge.example"
    supplier.phone = "+971500009999"
    supplier.address = "Dubai Wholesale Market"
    supplier.status = "active"
    supplier.notes = "Demo supplier for the Frabby Footwear presentation catalog."
    session.flush()
    return supplier


def _upsert_category(session: Session, client_id: str, name: str):
    from easy_ecom.data.store.postgres_models import CategoryModel

    slug = slugify_identifier(name, max_length=128, default="category")
    category = session.execute(
        select(CategoryModel).where(CategoryModel.client_id == client_id, CategoryModel.slug == slug)
    ).scalar_one_or_none()
    if category is None:
        category = CategoryModel(category_id=new_uuid(), client_id=client_id, name=name, slug=slug)
        session.add(category)
    category.name = name
    category.status = "active"
    category.notes = "Demo shoe-store category"
    session.flush()
    return category


def _upsert_product(
    session: Session,
    client_id: str,
    supplier: SupplierModel,
    category_by_name: dict[str, Any],
    product_data: DemoProduct,
) -> ProductModel:
    slug = slugify_identifier(product_data.name, max_length=128, default="shoe-product")
    product = session.execute(
        select(ProductModel).where(ProductModel.client_id == client_id, ProductModel.slug == slug)
    ).scalar_one_or_none()
    default_price = min(variant.price for variant in product_data.variants)
    min_price = min(variant.price - Decimal("20") for variant in product_data.variants)
    if product is None:
        product = ProductModel(
            product_id=new_uuid(),
            client_id=client_id,
            slug=slug,
            name=product_data.name,
        )
        session.add(product)
    product.supplier_id = supplier.supplier_id
    product.category_id = category_by_name[product_data.category].category_id
    product.name = product_data.name
    product.sku_root = product_data.sku_root
    product.brand = product_data.brand
    product.description = product_data.description
    product.status = "active"
    product.default_price_amount = _money(default_price)
    product.min_price_amount = _money(min_price)
    product.max_discount_percent = product_data.max_discount_percent
    session.flush()
    return product


def _upsert_variant(session: Session, client_id: str, product: ProductModel, variant_data: DemoVariant) -> ProductVariantModel:
    variant = session.execute(
        select(ProductVariantModel).where(ProductVariantModel.client_id == client_id, ProductVariantModel.sku == variant_data.sku)
    ).scalar_one_or_none()
    if variant is None:
        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=client_id,
            product_id=product.product_id,
            sku=variant_data.sku,
            title=variant_data.title,
        )
        session.add(variant)
    variant.product_id = product.product_id
    variant.title = variant_data.title
    variant.option_values_json = {
        "size": variant_data.size,
        "color": variant_data.color,
        "fit": "Regular",
        "material": "Mixed",
    }
    variant.status = "active"
    variant.cost_amount = _money(variant_data.cost)
    variant.price_amount = _money(variant_data.price)
    variant.min_price_amount = _money(variant_data.price - Decimal("20"))
    variant.reorder_level = variant_data.reorder_level
    session.flush()
    return variant


def _current_stock(session: Session, client_id: str, variant_id: str, location_id: str) -> Decimal:
    return as_decimal(
        session.execute(
            select(func.coalesce(func.sum(InventoryLedgerModel.quantity_delta), ZERO)).where(
                InventoryLedgerModel.client_id == client_id,
                InventoryLedgerModel.variant_id == variant_id,
                InventoryLedgerModel.location_id == location_id,
            )
        ).scalar_one()
    )


def _set_stock_target(
    session: Session,
    *,
    client_id: str,
    variant: ProductVariantModel,
    location: LocationModel,
    target_stock: Decimal,
    created_by_user_id: str | None,
) -> bool:
    current = _current_stock(session, client_id, str(variant.variant_id), str(location.location_id))
    delta = _quantity(target_stock - current)
    if delta == ZERO:
        return False
    session.add(
        InventoryLedgerModel(
            entry_id=new_uuid(),
            client_id=client_id,
            variant_id=variant.variant_id,
            location_id=location.location_id,
            movement_type="adjustment",
            reference_type="demo_backfill",
            reference_id=DEMO_REFERENCE_ID,
            reference_line_id=variant.sku,
            quantity_delta=delta,
            unit_cost_amount=variant.cost_amount,
            unit_price_amount=variant.price_amount,
            reason="Set demo shoe-store stock target",
            created_by_user_id=created_by_user_id,
        )
    )
    return True


def _upsert_customers(session: Session, client_id: str) -> dict[str, CustomerModel]:
    customers: dict[str, CustomerModel] = {}
    for payload in DEMO_CUSTOMERS:
        customer = session.execute(
            select(CustomerModel).where(CustomerModel.client_id == client_id, CustomerModel.code == payload["code"])
        ).scalar_one_or_none()
        if customer is None:
            customer = CustomerModel(customer_id=new_uuid(), client_id=client_id, code=payload["code"])
            session.add(customer)
        customer.name = payload["name"]
        customer.email = payload["email"]
        customer.email_normalized = normalize_email(payload["email"])
        customer.phone = payload["phone"]
        customer.phone_normalized = normalize_phone(payload["phone"])
        customer.whatsapp_number = normalize_phone(payload["phone"])
        customer.address = payload["address"]
        customer.status = "active"
        customer.notes = payload["notes"]
        customers[payload["code"]] = customer
    session.flush()
    return customers


def _create_demo_orders(
    session: Session,
    *,
    client_id: str,
    location: LocationModel,
    customers: dict[str, CustomerModel],
    variants_by_sku: dict[str, ProductVariantModel],
    created_by_user_id: str | None,
) -> int:
    created = 0
    now = datetime.now(UTC)
    for payload in DEMO_ORDERS:
        existing = session.execute(
            select(SalesOrderModel.sales_order_id).where(
                SalesOrderModel.client_id == client_id,
                SalesOrderModel.order_number == payload["order_number"],
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue
        customer = customers[payload["customer_code"]]
        order = SalesOrderModel(
            sales_order_id=new_uuid(),
            client_id=client_id,
            customer_id=customer.customer_id,
            location_id=location.location_id,
            order_number=payload["order_number"],
            status="completed",
            payment_status=payload["payment_status"],
            shipment_status="fulfilled",
            ordered_at=now - timedelta(days=int(payload["days_ago"])),
            confirmed_at=now - timedelta(days=int(payload["days_ago"])),
            notes="Demo fulfilled shoe-store order",
            created_by_user_id=created_by_user_id,
            source_type="manual",
            subtotal_amount=ZERO,
            discount_amount=ZERO,
            total_amount=ZERO,
            paid_amount=payload["paid_amount"],
        )
        session.add(order)
        session.flush()
        total = ZERO
        for sku, quantity in payload["lines"]:
            variant = variants_by_sku[sku]
            line_total = _money(as_decimal(quantity) * as_decimal(variant.price_amount))
            total += line_total
            item = SalesOrderItemModel(
                sales_order_item_id=new_uuid(),
                client_id=client_id,
                sales_order_id=order.sales_order_id,
                variant_id=variant.variant_id,
                quantity=quantity,
                quantity_fulfilled=quantity,
                quantity_cancelled=ZERO,
                unit_price_amount=variant.price_amount,
                discount_amount=ZERO,
                line_total_amount=line_total,
            )
            session.add(item)
            session.flush()
            session.add(
                InventoryLedgerModel(
                    entry_id=new_uuid(),
                    client_id=client_id,
                    variant_id=variant.variant_id,
                    location_id=location.location_id,
                    movement_type="sale_fulfilled",
                    reference_type="sales_order",
                    reference_id=str(order.sales_order_id),
                    reference_line_id=str(item.sales_order_item_id),
                    quantity_delta=-quantity,
                    unit_cost_amount=variant.cost_amount,
                    unit_price_amount=variant.price_amount,
                    reason="Demo fulfilled sale",
                    created_by_user_id=created_by_user_id,
                )
            )
        order.subtotal_amount = _money(total)
        order.total_amount = _money(total)
        session.add(
            PaymentModel(
                payment_id=new_uuid(),
                client_id=client_id,
                sales_order_id=order.sales_order_id,
                status="completed",
                direction="in",
                method="card",
                amount=_money(payload["paid_amount"]),
                paid_at=order.confirmed_at,
                reference=f"PAY-{payload['order_number']}",
                notes="Demo payment",
                created_by_user_id=created_by_user_id,
            )
        )
        created += 1
    return created


def _upsert_playbook(session: Session, client_id: str) -> None:
    playbook = session.execute(
        select(AssistantPlaybookModel).where(AssistantPlaybookModel.client_id == client_id)
    ).scalar_one_or_none()
    if playbook is None:
        playbook = AssistantPlaybookModel(playbook_id=new_uuid(), client_id=client_id)
        session.add(playbook)
    playbook.status = "active"
    playbook.business_type = "shoe_store"
    playbook.brand_personality = "expert"
    playbook.custom_instructions = (
        "Frabby Footwear is a demo shoe store. Be polished, quick, and commercially helpful. "
        "Ask for shoe size, use case, color/style, fit preference, and budget when recommending. "
        "For exact price or stock, check tools first. If the customer is ready, offer to prepare a draft order."
    )
    playbook.forbidden_claims = (
        "Do not claim medical or orthopedic benefits. Do not promise delivery times, discounts, payment links, or fulfillment "
        "unless tenant policy or staff confirms it. Do not confirm orders; draft orders only."
    )
    playbook.sales_goals_json = {
        "upsell": True,
        "cross_sell": True,
        "promote_slow_stock": True,
        "protect_premium_positioning": True,
    }
    playbook.policy_json = {
        "delivery": "Standard UAE delivery is 1-3 business days after staff confirms the order.",
        "returns": "Unused shoes can be reviewed for exchange within 7 days if packaging is intact.",
        "payment": "Staff sends payment links after draft order review. Cash on delivery may be available by area.",
        "warranty": "Manufacturing defects are reviewed by staff with photos and order details.",
        "discounts": "Discounts are staff-approved. The assistant may suggest bundles but must not promise a discount.",
    }
    playbook.escalation_rules_json = {**DEFAULT_ESCALATION_RULES, "high_value_order": True, "unavailable_product": True}
    playbook.industry_template_json = INDUSTRY_TEMPLATES["shoe_store"]


def _upsert_demo_channel(session: Session, client_id: str, location: LocationModel, created_by_user_id: str | None) -> CustomerChannelModel:
    channel = session.execute(
        select(CustomerChannelModel).where(
            CustomerChannelModel.client_id == client_id,
            CustomerChannelModel.provider == "website",
            CustomerChannelModel.external_account_id == DEMO_CHANNEL_ACCOUNT_ID,
        )
    ).scalar_one_or_none()
    if channel is None:
        channel = CustomerChannelModel(
            channel_id=new_uuid(),
            client_id=client_id,
            provider="website",
            external_account_id=DEMO_CHANNEL_ACCOUNT_ID,
            webhook_key=f"cc_{new_uuid().replace('-', '')}",
            created_by_user_id=created_by_user_id,
        )
        session.add(channel)
    channel.display_name = "Frabby Footwear Website"
    channel.status = "active"
    channel.default_location_id = location.location_id
    channel.auto_send_enabled = True
    channel.config_json = {"demo_vertical": "shoe_store", "source": DEMO_REFERENCE_ID}
    session.flush()
    return channel


def _clean_test_customer_communication(session: Session, client_id: str) -> int:
    conversations = list(
        session.execute(
            select(CustomerConversationModel).where(
                CustomerConversationModel.client_id == client_id,
                CustomerConversationModel.external_sender_id.like("cc-test-%"),
            )
        ).scalars()
    )
    channels = list(
        session.execute(
            select(CustomerChannelModel).where(
                CustomerChannelModel.client_id == client_id,
                (
                    (CustomerChannelModel.external_account_id.like("cc-test-%"))
                    | (CustomerChannelModel.display_name.like("Website chat test%"))
                ),
            )
        ).scalars()
    )
    deleted = len(conversations) + len(channels)
    for conversation in conversations:
        session.delete(conversation)
    for channel in channels:
        session.delete(channel)
    return deleted


def backfill_shoe_store_demo(tenant_email: str, *, apply: bool) -> dict[str, Any]:
    engine = build_postgres_engine(settings)
    SessionFactory = build_session_factory(engine)
    with SessionFactory() as session:
        user = _tenant_user(session, tenant_email)
        client_id = str(user.client_id)
        client = session.execute(select(ClientModel).where(ClientModel.client_id == client_id)).scalar_one()
        location = _default_location(session, client_id)
        supplier = _upsert_supplier(session, client_id)
        category_by_name = {
            name: _upsert_category(session, client_id, name)
            for name in sorted({product.category for product in DEMO_PRODUCTS})
        }
        variants_by_sku: dict[str, ProductVariantModel] = {}
        products_upserted = 0
        variants_upserted = 0
        stock_adjustments = 0
        for product_data in DEMO_PRODUCTS:
            product = _upsert_product(session, client_id, supplier, category_by_name, product_data)
            products_upserted += 1
            for variant_data in product_data.variants:
                variant = _upsert_variant(session, client_id, product, variant_data)
                variants_by_sku[variant.sku] = variant
                variants_upserted += 1

        customers = _upsert_customers(session, client_id)
        orders_created = _create_demo_orders(
            session,
            client_id=client_id,
            location=location,
            customers=customers,
            variants_by_sku=variants_by_sku,
            created_by_user_id=str(user.user_id),
        )
        for product_data in DEMO_PRODUCTS:
            for variant_data in product_data.variants:
                if _set_stock_target(
                    session,
                    client_id=client_id,
                    variant=variants_by_sku[variant_data.sku],
                    location=location,
                    target_stock=variant_data.target_stock,
                    created_by_user_id=str(user.user_id),
                ):
                    stock_adjustments += 1

        cleaned_customer_comm = _clean_test_customer_communication(session, client_id)
        _upsert_playbook(session, client_id)
        channel = _upsert_demo_channel(session, client_id, location, str(user.user_id))

        client.business_name = "Frabby Footwear"
        client.currency_code = "AED"
        client.currency_symbol = "AED "
        client.timezone = "Asia/Dubai"
        client.website_url = "https://frabby-footwear.example"
        client.instagram_url = "https://instagram.com/frabbyfootwear"
        client.whatsapp_number = "+971501234567"
        client.notes = "Demo shoe-store tenant backfilled for EasyEcom assistant and operations presentation."

        summary = {
            "tenant_email": tenant_email,
            "client_id": client_id,
            "business_name": client.business_name,
            "location": location.name,
            "products": products_upserted,
            "variants": variants_upserted,
            "stock_adjustments": stock_adjustments,
            "customers": len(customers),
            "orders_created": orders_created,
            "cleaned_customer_communication_records": cleaned_customer_comm,
            "channel_display_name": channel.display_name,
            "channel_key": channel.webhook_key,
        }
        if apply:
            session.commit()
        else:
            session.rollback()
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill a tenant with idempotent shoe-store demo data.")
    parser.add_argument("--tenant-email", required=True, help="Owner/user email that identifies the target tenant.")
    parser.add_argument("--apply", action="store_true", help="Commit the backfill. Without this flag, the script rolls back.")
    args = parser.parse_args()

    summary = backfill_shoe_store_demo(args.tenant_email, apply=args.apply)
    mode = "applied" if args.apply else "dry_run"
    print(f"[demo-backfill] mode={mode}")
    for key, value in summary.items():
        print(f"[demo-backfill] {key}={value}")


if __name__ == "__main__":
    main()
