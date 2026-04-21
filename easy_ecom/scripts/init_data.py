from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.core.slugs import slugify_identifier
from easy_ecom.data.store.migrations import apply_sql_migrations
from easy_ecom.data.store.postgres import init_postgres_schema
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import (
    ClientModel,
    ClientSettingsModel,
    CustomerModel,
    ExpenseModel,
    FinanceTransactionLinkModel,
    FinanceTransactionModel,
    InventoryLedgerModel,
    LocationModel,
    PaymentModel,
    ProductModel,
    ProductVariantModel,
    PurchaseItemModel,
    PurchaseModel,
    RefundModel,
    RoleModel,
    SalesOrderItemModel,
    SalesOrderModel,
    SalesReturnItemModel,
    SalesReturnModel,
    SupplierModel,
    UserModel,
    UserRoleModel,
)
from easy_ecom.data.store.schema import ROLES_SEED

SAMPLE_PURCHASE_NUMBER = "PO-SAMPLE-2026-0001"


def _seed_sample_business_data(
    session,
    *,
    client_id: str,
    location_id: str,
    created_by_user_id: str | None,
) -> None:
    existing_seed = session.execute(
        select(PurchaseModel.purchase_id).where(
            PurchaseModel.client_id == client_id,
            PurchaseModel.purchase_number == SAMPLE_PURCHASE_NUMBER,
        )
    ).scalar_one_or_none()
    if existing_seed is not None:
        return

    now = datetime.now(UTC)
    supplier = SupplierModel(
        supplier_id=new_uuid(),
        client_id=client_id,
        name="Dhaka Trade House",
        code="SUP-DTH",
        contact_name="Nadia Rahman",
        email="nadia@dhakatrade.example",
        phone="+8801700000000",
        address="Tejgaon Industrial Area, Dhaka",
        status="active",
        notes="Primary footwear and accessories supplier",
    )
    session.add(supplier)
    session.flush()

    products: list[tuple[ProductModel, ProductVariantModel, Decimal, Decimal, Decimal]] = []
    product_templates = [
        ("Trail Runner", "TRAIL", "Easy Brand", Decimal("32"), Decimal("79"), Decimal("14"), Decimal("10")),
        ("City Backpack", "PACK", "Urban Gear", Decimal("21"), Decimal("55"), Decimal("8"), Decimal("6")),
        ("Hydra Bottle", "HYDRA", "Flow Labs", Decimal("6"), Decimal("18"), Decimal("25"), Decimal("20")),
        ("Core Tee", "CTEE", "Cotton Lab", Decimal("8"), Decimal("24"), Decimal("30"), Decimal("26")),
        ("Denim Jacket", "DNMJ", "North Line", Decimal("36"), Decimal("92"), Decimal("9"), Decimal("7")),
        ("Office Shirt", "OSRT", "Urban Tailor", Decimal("14"), Decimal("39"), Decimal("18"), Decimal("16")),
        ("Weekend Polo", "POLO", "Urban Tailor", Decimal("12"), Decimal("35"), Decimal("20"), Decimal("15")),
        ("Smart Chino", "CHNO", "Street Form", Decimal("19"), Decimal("52"), Decimal("13"), Decimal("11")),
        ("Summer Shorts", "SHRT", "Street Form", Decimal("11"), Decimal("31"), Decimal("17"), Decimal("14")),
        ("Yoga Leggings", "YOGA", "Flex Fit", Decimal("15"), Decimal("44"), Decimal("16"), Decimal("12")),
        ("Training Hoodie", "HOOD", "Flex Fit", Decimal("24"), Decimal("68"), Decimal("12"), Decimal("9")),
        ("Canvas Belt", "BELT", "Urban Gear", Decimal("5"), Decimal("16"), Decimal("22"), Decimal("18")),
        ("Leather Wallet", "WLTT", "Carry Co", Decimal("9"), Decimal("29"), Decimal("24"), Decimal("19")),
        ("Travel Pouch", "POUC", "Carry Co", Decimal("7"), Decimal("21"), Decimal("18"), Decimal("15")),
        ("Sport Socks", "SOCK", "Easy Brand", Decimal("3"), Decimal("11"), Decimal("40"), Decimal("34")),
        ("Cap Classic", "CAPC", "Easy Brand", Decimal("6"), Decimal("19"), Decimal("20"), Decimal("16")),
        ("Rain Shell", "RAIN", "North Line", Decimal("33"), Decimal("95"), Decimal("7"), Decimal("5")),
        ("Mini Speaker", "SPKR", "Sound Arc", Decimal("18"), Decimal("49"), Decimal("14"), Decimal("10")),
        ("Desk Lamp", "LAMP", "Home Shift", Decimal("12"), Decimal("36"), Decimal("15"), Decimal("12")),
        ("Aroma Candle", "CNDL", "Home Shift", Decimal("4"), Decimal("14"), Decimal("28"), Decimal("23")),
    ]

    product_by_name: dict[str, ProductModel] = {}
    for product_name, sku_root, brand, base_cost, base_price, qty_one, qty_two in product_templates:
        product = product_by_name.get(product_name)
        if product is None:
            product = ProductModel(
                product_id=new_uuid(),
                client_id=client_id,
                supplier_id=supplier.supplier_id,
                category_id=None,
                name=product_name,
                slug=f"{product_name.lower().replace(' ', '-')}-{sku_root.lower()}",
                sku_root=sku_root,
                brand=brand,
                description=f"{product_name} sample catalog row for demo operations.",
                status="active",
                default_price_amount=base_price,
                min_price_amount=(base_price - Decimal("8")),
                max_discount_percent=Decimal("15"),
            )
            product_by_name[product_name] = product
            session.add(product)
            session.flush()

        variant_specs = [
            ("M / Black", f"{sku_root}-M-BLK", base_cost, base_price, qty_one),
            ("L / Navy", f"{sku_root}-L-NVY", base_cost + Decimal("1"), base_price + Decimal("3"), qty_two),
        ]
        for title, sku, cost, price, received_qty in variant_specs:
            variant = ProductVariantModel(
                variant_id=new_uuid(),
                client_id=client_id,
                product_id=product.product_id,
                title=title,
                sku=sku,
                option_values_json={"title": title},
                status="active",
                cost_amount=cost,
                price_amount=price,
                min_price_amount=(price - Decimal("8")),
                reorder_level=Decimal("4"),
            )
            session.add(variant)
            products.append((product, variant, cost, price, received_qty))

    session.flush()

    purchase = PurchaseModel(
        purchase_id=new_uuid(),
        client_id=client_id,
        supplier_id=supplier.supplier_id,
        location_id=location_id,
        purchase_number=SAMPLE_PURCHASE_NUMBER,
        status="received",
        ordered_at=now - timedelta(days=14),
        received_at=now - timedelta(days=12),
        notes="Bootstrap sample inventory receipt",
        created_by_user_id=created_by_user_id,
        subtotal_amount=Decimal("0"),
        total_amount=Decimal("0"),
    )
    session.add(purchase)
    session.flush()

    purchase_total = Decimal("0")
    for _, variant, cost, price, received_qty in products:
        line_total = (received_qty * cost).quantize(Decimal("0.01"))
        purchase_total += line_total
        purchase_item = PurchaseItemModel(
            purchase_item_id=new_uuid(),
            client_id=client_id,
            purchase_id=purchase.purchase_id,
            variant_id=variant.variant_id,
            quantity=received_qty,
            received_quantity=received_qty,
            unit_cost_amount=cost,
            line_total_amount=line_total,
            notes="Sample seeded inbound stock",
        )
        session.add(purchase_item)
        session.flush()
        session.add(
            InventoryLedgerModel(
                entry_id=new_uuid(),
                client_id=client_id,
                variant_id=variant.variant_id,
                location_id=location_id,
                movement_type="stock_received",
                reference_type="purchase",
                reference_id=str(purchase.purchase_id),
                reference_line_id=str(purchase_item.purchase_item_id),
                quantity_delta=received_qty,
                unit_cost_amount=cost,
                unit_price_amount=price,
                reason="Sample baseline purchase receipt",
                created_by_user_id=created_by_user_id,
            )
        )

    purchase.subtotal_amount = purchase_total
    purchase.total_amount = purchase_total

    customer_amina = CustomerModel(
        customer_id=new_uuid(),
        client_id=client_id,
        code="CUS-AMINA",
        name="Amina Noor",
        email="amina.noor@example.com",
        email_normalized="amina.noor@example.com",
        phone="+971 50 100 2000",
        phone_normalized="971501002000",
        whatsapp_number="+971501002000",
        address="Dubai Marina",
        status="active",
    )
    customer_farhan = CustomerModel(
        customer_id=new_uuid(),
        client_id=client_id,
        code="CUS-FARHAN",
        name="Farhan Karim",
        email="farhan.karim@example.com",
        email_normalized="farhan.karim@example.com",
        phone="+971 55 444 8899",
        phone_normalized="971554448899",
        whatsapp_number="+971554448899",
        address="Sharjah Al Khan",
        status="active",
    )
    session.add_all([customer_amina, customer_farhan])
    session.flush()

    primary_variant = products[0][1]
    accessory_variant = products[4][1]

    completed_order = SalesOrderModel(
        sales_order_id=new_uuid(),
        client_id=client_id,
        customer_id=customer_amina.customer_id,
        location_id=location_id,
        order_number="SO-SAMPLE-2026-0001",
        status="completed",
        payment_status="partially_paid",
        shipment_status="fulfilled",
        ordered_at=now - timedelta(days=7),
        confirmed_at=now - timedelta(days=7),
        notes="Sample fulfilled order with partial payment",
        created_by_user_id=created_by_user_id,
        source_type="manual",
        subtotal_amount=Decimal("176"),
        discount_amount=Decimal("8"),
        total_amount=Decimal("168"),
        paid_amount=Decimal("120"),
    )
    session.add(completed_order)
    session.flush()
    completed_line = SalesOrderItemModel(
        sales_order_item_id=new_uuid(),
        client_id=client_id,
        sales_order_id=completed_order.sales_order_id,
        variant_id=primary_variant.variant_id,
        quantity=Decimal("2"),
        quantity_fulfilled=Decimal("2"),
        quantity_cancelled=Decimal("0"),
        unit_price_amount=Decimal("88"),
        discount_amount=Decimal("8"),
        line_total_amount=Decimal("168"),
    )
    session.add(completed_line)
    session.add(
        InventoryLedgerModel(
            entry_id=new_uuid(),
            client_id=client_id,
            variant_id=primary_variant.variant_id,
            location_id=location_id,
            movement_type="sale_fulfilled",
            reference_type="sales_order",
            reference_id=str(completed_order.sales_order_id),
            reference_line_id=str(completed_line.sales_order_item_id),
            quantity_delta=Decimal("-2"),
            unit_cost_amount=primary_variant.cost_amount,
            unit_price_amount=Decimal("88"),
            reason="Sample order fulfillment",
            created_by_user_id=created_by_user_id,
        )
    )

    confirmed_order = SalesOrderModel(
        sales_order_id=new_uuid(),
        client_id=client_id,
        customer_id=customer_farhan.customer_id,
        location_id=location_id,
        order_number="SO-SAMPLE-2026-0002",
        status="confirmed",
        payment_status="unpaid",
        shipment_status="pending",
        ordered_at=now - timedelta(days=2),
        confirmed_at=now - timedelta(days=2),
        notes="Sample confirmed order pending fulfillment",
        created_by_user_id=created_by_user_id,
        source_type="manual",
        subtotal_amount=Decimal("55"),
        discount_amount=Decimal("0"),
        total_amount=Decimal("55"),
        paid_amount=Decimal("0"),
    )
    session.add(confirmed_order)
    session.flush()
    session.add(
        SalesOrderItemModel(
            sales_order_item_id=new_uuid(),
            client_id=client_id,
            sales_order_id=confirmed_order.sales_order_id,
            variant_id=accessory_variant.variant_id,
            quantity=Decimal("1"),
            quantity_fulfilled=Decimal("0"),
            quantity_cancelled=Decimal("0"),
            unit_price_amount=Decimal("55"),
            discount_amount=Decimal("0"),
            line_total_amount=Decimal("55"),
        )
    )

    sales_return = SalesReturnModel(
        sales_return_id=new_uuid(),
        client_id=client_id,
        sales_order_id=completed_order.sales_order_id,
        customer_id=customer_amina.customer_id,
        return_number="RT-SAMPLE-2026-0001",
        status="received",
        refund_status="paid",
        requested_at=now - timedelta(days=5),
        approved_at=now - timedelta(days=5),
        received_at=now - timedelta(days=4),
        notes="Sample return with restock and refund",
        created_by_user_id=created_by_user_id,
        subtotal_amount=Decimal("84"),
        refund_amount=Decimal("84"),
    )
    session.add(sales_return)
    session.flush()
    sales_return_item = SalesReturnItemModel(
        sales_return_item_id=new_uuid(),
        client_id=client_id,
        sales_return_id=sales_return.sales_return_id,
        sales_order_item_id=completed_line.sales_order_item_id,
        variant_id=primary_variant.variant_id,
        quantity=Decimal("1"),
        restock_quantity=Decimal("1"),
        unit_refund_amount=Decimal("84"),
        disposition="restock",
    )
    session.add(sales_return_item)
    session.add(
        InventoryLedgerModel(
            entry_id=new_uuid(),
            client_id=client_id,
            variant_id=primary_variant.variant_id,
            location_id=location_id,
            movement_type="sales_return_restock",
            reference_type="sales_return",
            reference_id=str(sales_return.sales_return_id),
            reference_line_id=str(sales_return_item.sales_return_item_id),
            quantity_delta=Decimal("1"),
            unit_cost_amount=primary_variant.cost_amount,
            unit_price_amount=Decimal("84"),
            reason="Sample return restock",
            created_by_user_id=created_by_user_id,
        )
    )
    session.add(
        RefundModel(
            refund_id=new_uuid(),
            client_id=client_id,
            sales_return_id=sales_return.sales_return_id,
            payment_id=None,
            status="completed",
            amount=Decimal("84"),
            refunded_at=now - timedelta(days=4),
            reason="Sample refund payout",
            created_by_user_id=created_by_user_id,
        )
    )
    session.add(
        PaymentModel(
            payment_id=new_uuid(),
            client_id=client_id,
            sales_order_id=completed_order.sales_order_id,
            sales_return_id=None,
            status="completed",
            direction="in",
            method="cash",
            amount=Decimal("120"),
            paid_at=now - timedelta(days=6),
            reference="PAY-SAMPLE-2026-0001",
            notes="Sample partial collection",
            created_by_user_id=created_by_user_id,
        )
    )
    session.add(
        ExpenseModel(
            expense_id=new_uuid(),
            client_id=client_id,
            expense_number="EXP-SAMPLE-2026-0001",
            category="operations",
            description="Packaging, courier drop-off and petty cash expenses",
            vendor_name="City Courier & Supplies",
            amount=Decimal("48"),
            incurred_at=now - timedelta(days=3),
            payment_status="paid",
            created_by_user_id=created_by_user_id,
        )
    )

    finance_rows = [
        ("sale_fulfillment", str(completed_order.sales_order_id), "in", Decimal("168"), "SO-SAMPLE-2026-0001", "Recognized on fulfillment", "customer", str(customer_amina.customer_id), customer_amina.name, now - timedelta(days=7)),
        ("manual_payment", str(completed_order.sales_order_id), "in", Decimal("120"), "PAY-SAMPLE-2026-0001", "Cash collection for order", "customer", str(customer_amina.customer_id), customer_amina.name, now - timedelta(days=6)),
        ("return_refund", str(sales_return.sales_return_id), "out", Decimal("84"), "RF-SAMPLE-2026-0001", "Refund paid for return", "customer", str(customer_amina.customer_id), customer_amina.name, now - timedelta(days=4)),
        ("manual_expense", None, "out", Decimal("48"), "EXP-SAMPLE-2026-0001", "Operational expense payment", "vendor", None, "City Courier & Supplies", now - timedelta(days=3)),
    ]
    for origin_type, origin_id, direction, amount, reference, note, counterparty_type, counterparty_id, counterparty_name, occurred_at in finance_rows:
        transaction = FinanceTransactionModel(
            transaction_id=new_uuid(),
            client_id=client_id,
            origin_type=origin_type,
            origin_id=origin_id,
            direction=direction,
            status="posted",
            occurred_at=occurred_at,
            amount=amount,
            currency_code="USD",
            reference=reference,
            note=note,
            counterparty_type=counterparty_type,
            counterparty_id=counterparty_id,
            counterparty_name=counterparty_name,
            created_by_user_id=created_by_user_id,
        )
        session.add(transaction)
        session.flush()
        if origin_id:
            session.add(
                FinanceTransactionLinkModel(
                    finance_transaction_link_id=new_uuid(),
                    client_id=client_id,
                    transaction_id=transaction.transaction_id,
                    origin_type=origin_type,
                    origin_id=origin_id,
                )
            )


def _bootstrap_schema(engine) -> None:
    if settings.is_sqlite:
        init_postgres_schema(engine)
        return
    apply_sql_migrations(engine)


def main() -> None:
    engine = build_postgres_engine(settings)
    _bootstrap_schema(engine)
    session_factory = build_session_factory(engine)

    with session_factory() as session:
        global_client = session.execute(
            select(ClientModel).where(ClientModel.client_id == settings.global_client_id)
        ).scalar_one_or_none()
        if global_client is None:
            session.add(
                ClientModel(
                    client_id=settings.global_client_id,
                    slug=settings.global_client_slug,
                    business_name="EasyEcom Global",
                    contact_name="EasyEcom",
                    owner_name="EasyEcom",
                    email=settings.super_admin_email.strip().lower(),
                    currency_code="USD",
                    currency_symbol="$",
                    timezone="UTC",
                    status="active",
                )
            )

        for role in ROLES_SEED:
            existing_role = session.execute(
                select(RoleModel).where(RoleModel.role_code == role["role_code"])
            ).scalar_one_or_none()
            if existing_role is None:
                session.add(RoleModel(**role))

        existing_settings = session.execute(
            select(ClientSettingsModel).where(ClientSettingsModel.client_id == settings.global_client_id)
        ).scalar_one_or_none()
        if existing_settings is None:
            session.add(
                ClientSettingsModel(
                    client_settings_id=new_uuid(),
                    client_id=settings.global_client_id,
                    low_stock_threshold=Decimal("5"),
                    allow_backorder=settings.allow_backorder,
                    default_location_name="Global Warehouse",
                    require_discount_approval=False,
                    order_prefix="SO",
                    purchase_prefix="PO",
                    return_prefix="RT",
                )
            )

        existing_location = session.execute(
            select(LocationModel).where(
                LocationModel.client_id == settings.global_client_id,
                LocationModel.code == "GLOBAL",
            )
        ).scalar_one_or_none()
        if existing_location is None:
            existing_location = LocationModel(
                location_id=new_uuid(),
                client_id=settings.global_client_id,
                name="Global Warehouse",
                code="GLOBAL",
                is_default=True,
                status="active",
            )
            session.add(existing_location)
            session.flush()
        global_location_id = existing_location.location_id

        admin_email = settings.super_admin_email.strip().lower()
        admin_password = settings.super_admin_password
        admin_id: str | None = None
        if admin_email and admin_password:
            existing_user = session.execute(
                select(UserModel).where(UserModel.email == admin_email)
            ).scalar_one_or_none()
            if existing_user is None:
                admin_id = new_uuid()
                session.add(
                    UserModel(
                        user_id=admin_id,
                        user_code=slugify_identifier(
                            f"{settings.global_client_slug}-super-admin-super-admin",
                            max_length=160,
                            default="super-admin",
                        ),
                        client_id=settings.global_client_id,
                        name="Super Admin",
                        email=admin_email,
                        password="",
                        password_hash=hash_password(admin_password),
                        is_active=True,
                    )
                )
                session.add(UserRoleModel(user_id=admin_id, role_code="SUPER_ADMIN"))
            else:
                admin_id = str(existing_user.user_id)

        _seed_sample_business_data(
            session,
            client_id=settings.global_client_id,
            location_id=str(global_location_id),
            created_by_user_id=admin_id,
        )
        if admin_email:
            admin_user = session.execute(
                select(UserModel).where(UserModel.email == admin_email)
            ).scalar_one_or_none()
            if admin_user is not None and str(admin_user.client_id) != settings.global_client_id:
                owner_client_id = str(admin_user.client_id)
                owner_settings = session.execute(
                    select(ClientSettingsModel).where(ClientSettingsModel.client_id == owner_client_id)
                ).scalar_one_or_none()
                if owner_settings is None:
                    session.add(
                        ClientSettingsModel(
                            client_settings_id=new_uuid(),
                            client_id=owner_client_id,
                            low_stock_threshold=Decimal("5"),
                            allow_backorder=settings.allow_backorder,
                            default_location_name="Main Warehouse",
                            require_discount_approval=False,
                            order_prefix="SO",
                            purchase_prefix="PO",
                            return_prefix="RT",
                        )
                    )
                owner_location = session.execute(
                    select(LocationModel)
                    .where(LocationModel.client_id == owner_client_id)
                    .order_by(LocationModel.is_default.desc(), LocationModel.created_at.asc())
                ).scalars().first()
                if owner_location is None:
                    owner_location = LocationModel(
                        location_id=new_uuid(),
                        client_id=owner_client_id,
                        name="Main Warehouse",
                        code="MAIN",
                        is_default=True,
                        status="active",
                    )
                    session.add(owner_location)
                    session.flush()
                _seed_sample_business_data(
                    session,
                    client_id=owner_client_id,
                    location_id=str(owner_location.location_id),
                    created_by_user_id=str(admin_user.user_id),
                )

        if settings.create_default_client:
            default_slug = "default"
            default_client = session.execute(
                select(ClientModel).where(ClientModel.slug == default_slug)
            ).scalar_one_or_none()
            if default_client is None:
                default_client_id = new_uuid()
                session.add(
                    ClientModel(
                        client_id=default_client_id,
                        slug=default_slug,
                        business_name="Default Client",
                        contact_name="Owner",
                        owner_name="Owner",
                        email="owner@example.com",
                        currency_code="USD",
                        currency_symbol="$",
                        timezone="UTC",
                        status="active",
                    )
                )
                session.add(
                    ClientSettingsModel(
                        client_settings_id=new_uuid(),
                        client_id=default_client_id,
                        low_stock_threshold=Decimal("5"),
                        allow_backorder=settings.allow_backorder,
                        default_location_name="Main Warehouse",
                        require_discount_approval=False,
                        order_prefix="SO",
                        purchase_prefix="PO",
                        return_prefix="RT",
                    )
                )
                session.add(
                    LocationModel(
                        location_id=new_uuid(),
                        client_id=default_client_id,
                        name="Main Warehouse",
                        code="MAIN",
                        is_default=True,
                        status="active",
                    )
                )
                session.flush()
            else:
                default_client_id = str(default_client.client_id)
                existing_settings = session.execute(
                    select(ClientSettingsModel).where(ClientSettingsModel.client_id == default_client_id)
                ).scalar_one_or_none()
                if existing_settings is None:
                    session.add(
                        ClientSettingsModel(
                            client_settings_id=new_uuid(),
                            client_id=default_client_id,
                            low_stock_threshold=Decimal("5"),
                            allow_backorder=settings.allow_backorder,
                            default_location_name="Main Warehouse",
                            require_discount_approval=False,
                            order_prefix="SO",
                            purchase_prefix="PO",
                            return_prefix="RT",
                        )
                    )
            default_location = session.execute(
                select(LocationModel).where(
                    LocationModel.client_id == default_client_id,
                    LocationModel.code == "MAIN",
                )
            ).scalar_one_or_none()
            if default_location is None:
                default_location = LocationModel(
                    location_id=new_uuid(),
                    client_id=default_client_id,
                    name="Main Warehouse",
                    code="MAIN",
                    is_default=True,
                    status="active",
                )
                session.add(default_location)
                session.flush()
            default_owner = session.execute(
                select(UserModel.user_id)
                .where(UserModel.client_id == default_client_id, UserModel.is_active.is_(True))
                .limit(1)
            ).scalar_one_or_none()
            _seed_sample_business_data(
                session,
                client_id=default_client_id,
                location_id=str(default_location.location_id),
                created_by_user_id=str(default_owner) if default_owner else None,
            )

        session.commit()


if __name__ == "__main__":
    main()
