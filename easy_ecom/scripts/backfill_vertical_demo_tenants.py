from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from easy_ecom.core.config import settings
from easy_ecom.core.ids import new_uuid
from easy_ecom.core.security import hash_password
from easy_ecom.core.slugs import slugify_identifier
from easy_ecom.core.time_utils import now_utc
from easy_ecom.data.repos.postgres.code_factory import generate_unique_client_code, generate_unique_user_code
from easy_ecom.data.store.postgres_db import build_postgres_engine, build_session_factory
from easy_ecom.data.store.postgres_models import (
    AssistantPlaybookModel,
    CategoryModel,
    ClientModel,
    ClientSettingsModel,
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
    UserRoleModel,
)
from easy_ecom.domain.services.commerce_service import ZERO, as_decimal, normalize_email, normalize_phone
from easy_ecom.domain.services.customer_communication_service import DEFAULT_ESCALATION_RULES, INDUSTRY_TEMPLATES


DEMO_REFERENCE_PREFIX = "DEMO-VERTICAL-20260424"
DEMO_SENDER_PREFIX = "enterprise-demo-"


@dataclass(frozen=True)
class VerticalVariant:
    title: str
    sku: str
    options: dict[str, str]
    cost: Decimal
    price: Decimal
    target_stock: Decimal
    reorder_level: Decimal = Decimal("4")


@dataclass(frozen=True)
class VerticalProduct:
    name: str
    sku_root: str
    brand: str
    category: str
    description: str
    variants: tuple[VerticalVariant, ...]
    max_discount_percent: Decimal = Decimal("10")


@dataclass(frozen=True)
class VerticalCustomer:
    code: str
    name: str
    email: str
    phone: str
    address: str
    notes: str


@dataclass(frozen=True)
class VerticalOrder:
    order_number: str
    customer_code: str
    days_ago: int
    payment_status: str
    paid_amount: Decimal
    lines: tuple[tuple[str, Decimal], ...]


@dataclass(frozen=True)
class VerticalDemoSpec:
    tenant_email: str
    owner_name: str
    business_name: str
    business_type: str
    brand_personality: str
    contact_phone: str
    location_name: str
    supplier_name: str
    supplier_code: str
    currency_code: str
    currency_symbol: str
    timezone: str
    website_url: str
    instagram_url: str
    whatsapp_number: str
    custom_instructions: str
    forbidden_claims: str
    policies: dict[str, str]
    products: tuple[VerticalProduct, ...]
    customers: tuple[VerticalCustomer, ...]
    orders: tuple[VerticalOrder, ...]


def _d(value: str) -> Decimal:
    return Decimal(value)


DEMO_SPECS: tuple[VerticalDemoSpec, ...] = (
    VerticalDemoSpec(
        tenant_email="demo.petpals@easy-ecom.online",
        owner_name="PetPals Owner",
        business_name="PetPals Food Store",
        business_type="pet_food",
        brand_personality="expert",
        contact_phone="+971501010101",
        location_name="PetPals Demo Store",
        supplier_name="Healthy Paws Wholesale",
        supplier_code="DEMO-PET-SUP",
        currency_code="AED",
        currency_symbol="AED",
        timezone="Asia/Dubai",
        website_url="https://petpals-demo.example",
        instagram_url="https://instagram.com/petpalsdemo",
        whatsapp_number="+971501010101",
        custom_instructions=(
            "PetPals sells pet food and treats. Be caring, practical, and safety-aware. "
            "Ask pet type, age, breed or size, current diet, allergies, and health concerns before recommending."
        ),
        forbidden_claims="Do not diagnose pets or claim food cures illness. For symptoms, advise a veterinarian.",
        policies={
            "delivery": "Standard UAE delivery is 1-2 business days after staff confirms the order.",
            "returns": "Unopened food can be reviewed for exchange within 7 days.",
            "payment": "Staff sends payment links after draft order review.",
            "warranty": "Damaged packaging is reviewed by staff with photos.",
            "discounts": "Bundle discounts require staff approval.",
        },
        products=(
            VerticalProduct(
                "Pawsome Salmon Puppy Food",
                "PSP",
                "Pawsome",
                "Dog Food",
                "Salmon puppy food for growing dogs. Not a medical diet.",
                (
                    VerticalVariant("2kg Bag", "PSP-SAL-PUP-2KG", {"size": "2kg", "flavor": "Salmon", "life_stage": "Puppy"}, _d("39"), _d("89"), _d("18")),
                    VerticalVariant("10kg Bag", "PSP-SAL-PUP-10KG", {"size": "10kg", "flavor": "Salmon", "life_stage": "Puppy"}, _d("170"), _d("349"), _d("7")),
                ),
            ),
            VerticalProduct(
                "Gentle Lamb Adult Dog Food",
                "GLA",
                "Pawsome",
                "Dog Food",
                "Lamb adult dog food for daily feeding. Ask staff for ingredient details.",
                (
                    VerticalVariant("2kg Bag", "GLA-LAMB-2KG", {"size": "2kg", "flavor": "Lamb", "life_stage": "Adult"}, _d("34"), _d("79"), _d("20")),
                    VerticalVariant("12kg Bag", "GLA-LAMB-12KG", {"size": "12kg", "flavor": "Lamb", "life_stage": "Adult"}, _d("185"), _d("379"), _d("6")),
                ),
            ),
            VerticalProduct(
                "Whisker Tuna Cat Food",
                "WTC",
                "Whisker",
                "Cat Food",
                "Tuna cat food for adult cats.",
                (
                    VerticalVariant("1.5kg Bag", "WTC-TUNA-1.5KG", {"size": "1.5kg", "flavor": "Tuna", "pet": "Cat"}, _d("26"), _d("65"), _d("15")),
                    VerticalVariant("6kg Bag", "WTC-TUNA-6KG", {"size": "6kg", "flavor": "Tuna", "pet": "Cat"}, _d("88"), _d("189"), _d("9")),
                ),
            ),
            VerticalProduct(
                "Duck Training Treats",
                "DTT",
                "TreatTrail",
                "Treats",
                "Small duck training treats for dogs.",
                (
                    VerticalVariant("300g Pouch", "DTT-DUCK-300G", {"size": "300g", "flavor": "Duck"}, _d("12"), _d("39"), _d("28")),
                    VerticalVariant("600g Pouch", "DTT-DUCK-600G", {"size": "600g", "flavor": "Duck"}, _d("21"), _d("69"), _d("16")),
                ),
            ),
        ),
        customers=(
            VerticalCustomer("DEMO-PET-MINA", "Mina Joseph", "mina.pet.demo@example.com", "+971501111001", "Dubai Hills", "Dog owner, asks about puppy food."),
            VerticalCustomer("DEMO-PET-ALI", "Ali Hassan", "ali.pet.demo@example.com", "+971501111002", "Sharjah", "Cat owner, prefers tuna products."),
        ),
        orders=(
            VerticalOrder("SO-DEMO-PET-0001", "DEMO-PET-MINA", 8, "paid", _d("128"), (("PSP-SAL-PUP-2KG", _d("1")), ("DTT-DUCK-300G", _d("1")))),
            VerticalOrder("SO-DEMO-PET-0002", "DEMO-PET-ALI", 4, "paid", _d("189"), (("WTC-TUNA-6KG", _d("1")),)),
        ),
    ),
    VerticalDemoSpec(
        tenant_email="demo.fashion@easy-ecom.online",
        owner_name="Urban Thread Owner",
        business_name="Urban Thread Boutique",
        business_type="fashion",
        brand_personality="premium",
        contact_phone="+971502020202",
        location_name="Urban Thread Demo Showroom",
        supplier_name="StyleLine Apparel Supply",
        supplier_code="DEMO-FASHION-SUP",
        currency_code="AED",
        currency_symbol="AED",
        timezone="Asia/Dubai",
        website_url="https://urbanthread-demo.example",
        instagram_url="https://instagram.com/urbanthreaddemo",
        whatsapp_number="+971502020202",
        custom_instructions="Urban Thread sells smart casual fashion. Ask size, color, occasion, fit preference, and budget before recommending.",
        forbidden_claims="Do not guarantee exact fit. Confirm size and color before stock or price promises.",
        policies={
            "delivery": "Dubai delivery is usually 1-2 business days after staff confirmation.",
            "returns": "Unworn items with tags can be reviewed for exchange within 7 days.",
            "payment": "Payment links are sent by staff after draft order review.",
            "warranty": "Manufacturing defects are reviewed with photos.",
            "discounts": "Discounts are staff-approved only.",
        },
        products=(
            VerticalProduct(
                "Ariya Linen Blazer",
                "ALB",
                "Ariya",
                "Blazers",
                "Lightweight linen blazer for work and events.",
                (
                    VerticalVariant("S / Sand", "ALB-S-SAND", {"size": "S", "color": "Sand", "fit": "Regular"}, _d("95"), _d("219"), _d("8")),
                    VerticalVariant("M / Sand", "ALB-M-SAND", {"size": "M", "color": "Sand", "fit": "Regular"}, _d("95"), _d("219"), _d("11")),
                    VerticalVariant("M / Black", "ALB-M-BLK", {"size": "M", "color": "Black", "fit": "Regular"}, _d("98"), _d("229"), _d("7")),
                ),
            ),
            VerticalProduct(
                "Nova Satin Midi Dress",
                "NSD",
                "Nova",
                "Dresses",
                "Satin midi dress for evening occasions.",
                (
                    VerticalVariant("S / Emerald", "NSD-S-EMR", {"size": "S", "color": "Emerald", "occasion": "Evening"}, _d("80"), _d("189"), _d("10")),
                    VerticalVariant("M / Emerald", "NSD-M-EMR", {"size": "M", "color": "Emerald", "occasion": "Evening"}, _d("80"), _d("189"), _d("12")),
                ),
            ),
            VerticalProduct(
                "CoreFlex Straight Jeans",
                "CFJ",
                "CoreFlex",
                "Jeans",
                "Straight-leg denim with comfortable stretch.",
                (
                    VerticalVariant("30 / Indigo", "CFJ-30-IND", {"waist": "30", "color": "Indigo", "fit": "Straight"}, _d("58"), _d("139"), _d("14")),
                    VerticalVariant("32 / Indigo", "CFJ-32-IND", {"waist": "32", "color": "Indigo", "fit": "Straight"}, _d("58"), _d("139"), _d("13")),
                ),
            ),
            VerticalProduct(
                "Minimal White Oxford Shirt",
                "MWO",
                "Minimal",
                "Shirts",
                "Crisp white shirt for office and smart casual outfits.",
                (
                    VerticalVariant("M / White", "MWO-M-WHT", {"size": "M", "color": "White", "fit": "Slim"}, _d("35"), _d("89"), _d("20")),
                    VerticalVariant("L / White", "MWO-L-WHT", {"size": "L", "color": "White", "fit": "Slim"}, _d("35"), _d("89"), _d("18")),
                ),
            ),
        ),
        customers=(
            VerticalCustomer("DEMO-FASH-LINA", "Lina Karim", "lina.fashion.demo@example.com", "+971502222001", "JLT", "Prefers premium office wear."),
            VerticalCustomer("DEMO-FASH-NORA", "Nora Saleh", "nora.fashion.demo@example.com", "+971502222002", "Mirdif", "Looks for event dresses."),
        ),
        orders=(
            VerticalOrder("SO-DEMO-FASHION-0001", "DEMO-FASH-LINA", 9, "paid", _d("308"), (("ALB-M-SAND", _d("1")), ("MWO-M-WHT", _d("1")))),
            VerticalOrder("SO-DEMO-FASHION-0002", "DEMO-FASH-NORA", 5, "paid", _d("189"), (("NSD-M-EMR", _d("1")),)),
        ),
    ),
    VerticalDemoSpec(
        tenant_email="demo.electronics@easy-ecom.online",
        owner_name="Circuit House Owner",
        business_name="Circuit House Electronics",
        business_type="electronics",
        brand_personality="expert",
        contact_phone="+971503030303",
        location_name="Circuit House Demo Store",
        supplier_name="Gulf Tech Distribution",
        supplier_code="DEMO-ELEC-SUP",
        currency_code="AED",
        currency_symbol="AED",
        timezone="Asia/Dubai",
        website_url="https://circuithouse-demo.example",
        instagram_url="https://instagram.com/circuithousedemo",
        whatsapp_number="+971503030303",
        custom_instructions="Circuit House sells electronics accessories. Ask device model, compatibility need, warranty preference, and budget before recommending.",
        forbidden_claims="Do not claim compatibility unless product data supports it. Safety concerns must go to staff.",
        policies={
            "delivery": "UAE delivery is 1-3 business days after staff confirmation.",
            "returns": "Unused sealed accessories can be reviewed within 7 days.",
            "payment": "Staff sends payment links after draft order review.",
            "warranty": "Warranty terms depend on product and must be confirmed by staff.",
            "discounts": "Bundle pricing is staff-approved.",
        },
        products=(
            VerticalProduct(
                "VoltPro 65W USB-C Charger",
                "VPC",
                "VoltPro",
                "Chargers",
                "65W USB-C charger for phones, tablets, and compatible USB-C laptops.",
                (
                    VerticalVariant("White / 65W", "VPC-65W-WHT", {"color": "White", "wattage": "65W", "connector": "USB-C"}, _d("55"), _d("129"), _d("18")),
                    VerticalVariant("Black / 65W", "VPC-65W-BLK", {"color": "Black", "wattage": "65W", "connector": "USB-C"}, _d("55"), _d("129"), _d("16")),
                ),
            ),
            VerticalProduct(
                "ShieldCase iPhone 15",
                "SCI",
                "ShieldCase",
                "Phone Cases",
                "Protective case for iPhone 15.",
                (
                    VerticalVariant("Clear", "SCI-IP15-CLR", {"device": "iPhone 15", "color": "Clear"}, _d("18"), _d("59"), _d("25")),
                    VerticalVariant("Black", "SCI-IP15-BLK", {"device": "iPhone 15", "color": "Black"}, _d("18"), _d("59"), _d("22")),
                ),
            ),
            VerticalProduct(
                "PulseBuds Lite Wireless Earbuds",
                "PBL",
                "PulseBuds",
                "Audio",
                "Entry wireless earbuds with charging case.",
                (
                    VerticalVariant("White", "PBL-LITE-WHT", {"color": "White", "type": "Wireless earbuds"}, _d("72"), _d("169"), _d("11")),
                    VerticalVariant("Black", "PBL-LITE-BLK", {"color": "Black", "type": "Wireless earbuds"}, _d("72"), _d("169"), _d("13")),
                ),
            ),
            VerticalProduct(
                "PowerGo 20000mAh Power Bank",
                "PGP",
                "PowerGo",
                "Power Banks",
                "20,000mAh power bank with USB-C input/output.",
                (
                    VerticalVariant("Black", "PGP-20K-BLK", {"capacity": "20000mAh", "color": "Black"}, _d("86"), _d("199"), _d("10")),
                    VerticalVariant("Blue", "PGP-20K-BLU", {"capacity": "20000mAh", "color": "Blue"}, _d("86"), _d("199"), _d("8")),
                ),
            ),
        ),
        customers=(
            VerticalCustomer("DEMO-ELEC-SAM", "Samir Khan", "sam.electronics.demo@example.com", "+971503333001", "Business Bay", "Buys phone accessories."),
            VerticalCustomer("DEMO-ELEC-MIRA", "Mira Thomas", "mira.electronics.demo@example.com", "+971503333002", "Dubai Silicon Oasis", "Interested in chargers and power banks."),
        ),
        orders=(
            VerticalOrder("SO-DEMO-ELEC-0001", "DEMO-ELEC-SAM", 11, "paid", _d("118"), (("SCI-IP15-CLR", _d("1")), ("SCI-IP15-BLK", _d("1")))),
            VerticalOrder("SO-DEMO-ELEC-0002", "DEMO-ELEC-MIRA", 6, "paid", _d("328"), (("VPC-65W-WHT", _d("1")), ("PGP-20K-BLK", _d("1")))),
        ),
    ),
    VerticalDemoSpec(
        tenant_email="demo.cosmetics@easy-ecom.online",
        owner_name="GlowDerm Owner",
        business_name="GlowDerm Beauty",
        business_type="cosmetics",
        brand_personality="premium",
        contact_phone="+971504040404",
        location_name="GlowDerm Demo Studio",
        supplier_name="BeautyLab Distribution",
        supplier_code="DEMO-COS-SUP",
        currency_code="AED",
        currency_symbol="AED",
        timezone="Asia/Dubai",
        website_url="https://glowderm-demo.example",
        instagram_url="https://instagram.com/glowdermdemo",
        whatsapp_number="+971504040404",
        custom_instructions="GlowDerm sells skincare and cosmetics. Ask skin type, sensitivity, allergies, desired result, and budget before recommending.",
        forbidden_claims="Do not make medical claims, guarantee results, or advise treatment for skin conditions.",
        policies={
            "delivery": "Delivery is 1-3 business days after staff confirmation.",
            "returns": "Unopened cosmetics can be reviewed for exchange within 7 days.",
            "payment": "Staff sends payment links after draft order review.",
            "warranty": "Damaged products are reviewed with photos.",
            "discounts": "Promotions must be confirmed by staff.",
        },
        products=(
            VerticalProduct(
                "HydraCalm Gel Moisturizer",
                "HCG",
                "HydraCalm",
                "Moisturizers",
                "Light gel moisturizer for daily hydration. Check ingredients for sensitivities.",
                (
                    VerticalVariant("50ml", "HCG-GEL-50ML", {"size": "50ml", "skin_type": "Combination"}, _d("38"), _d("95"), _d("18")),
                    VerticalVariant("100ml", "HCG-GEL-100ML", {"size": "100ml", "skin_type": "Combination"}, _d("62"), _d("149"), _d("10")),
                ),
            ),
            VerticalProduct(
                "SunVeil SPF50 Sunscreen",
                "SVS",
                "SunVeil",
                "Sunscreen",
                "SPF50 sunscreen for daily use. Not a medical product.",
                (
                    VerticalVariant("Tinted / 50ml", "SVS-SPF50-TINT", {"size": "50ml", "finish": "Tinted"}, _d("44"), _d("109"), _d("16")),
                    VerticalVariant("Clear / 50ml", "SVS-SPF50-CLR", {"size": "50ml", "finish": "Clear"}, _d("42"), _d("105"), _d("20")),
                ),
            ),
            VerticalProduct(
                "GlowDrop Vitamin C Serum",
                "GVC",
                "GlowDrop",
                "Serums",
                "Vitamin C serum for cosmetic brightening goals. Patch test recommended.",
                (
                    VerticalVariant("30ml", "GVC-SERUM-30ML", {"size": "30ml", "active": "Vitamin C"}, _d("58"), _d("139"), _d("14")),
                    VerticalVariant("15ml", "GVC-SERUM-15ML", {"size": "15ml", "active": "Vitamin C"}, _d("34"), _d("79"), _d("12")),
                ),
            ),
            VerticalProduct(
                "PureFoam Gentle Cleanser",
                "PFC",
                "PureFoam",
                "Cleansers",
                "Gentle foam cleanser for daily use.",
                (
                    VerticalVariant("150ml", "PFC-CLEAN-150ML", {"size": "150ml", "skin_type": "All"}, _d("24"), _d("59"), _d("26")),
                    VerticalVariant("300ml", "PFC-CLEAN-300ML", {"size": "300ml", "skin_type": "All"}, _d("38"), _d("89"), _d("15")),
                ),
            ),
        ),
        customers=(
            VerticalCustomer("DEMO-COS-ANIKA", "Anika Roy", "anika.cos.demo@example.com", "+971504444001", "Jumeirah", "Asks about gentle skincare."),
            VerticalCustomer("DEMO-COS-HUDA", "Huda Nasser", "huda.cos.demo@example.com", "+971504444002", "Al Barsha", "Likes sunscreen and cleansers."),
        ),
        orders=(
            VerticalOrder("SO-DEMO-COS-0001", "DEMO-COS-ANIKA", 7, "paid", _d("154"), (("HCG-GEL-50ML", _d("1")), ("PFC-CLEAN-150ML", _d("1")))),
            VerticalOrder("SO-DEMO-COS-0002", "DEMO-COS-HUDA", 3, "paid", _d("105"), (("SVS-SPF50-CLR", _d("1")),)),
        ),
    ),
    VerticalDemoSpec(
        tenant_email="demo.grocery@easy-ecom.online",
        owner_name="FreshBasket Owner",
        business_name="FreshBasket Market",
        business_type="grocery",
        brand_personality="friendly",
        contact_phone="+971505050505",
        location_name="FreshBasket Demo Market",
        supplier_name="Daily Harvest Supply",
        supplier_code="DEMO-GROCERY-SUP",
        currency_code="AED",
        currency_symbol="AED",
        timezone="Asia/Dubai",
        website_url="https://freshbasket-demo.example",
        instagram_url="https://instagram.com/freshbasketdemo",
        whatsapp_number="+971505050505",
        custom_instructions="FreshBasket sells pantry groceries. Ask quantity, brand preference, delivery timing, and dietary restrictions before recommending.",
        forbidden_claims="Do not claim allergy-safe or ingredient facts unless product data or staff confirms it.",
        policies={
            "delivery": "Same-day delivery may be available by area after staff confirmation.",
            "returns": "Perishable returns require staff review.",
            "payment": "Staff sends payment links after draft order review.",
            "warranty": "Damaged items are reviewed with photos.",
            "discounts": "Bulk discounts require staff approval.",
        },
        products=(
            VerticalProduct(
                "Royal Grain Basmati Rice",
                "RGB",
                "Royal Grain",
                "Rice",
                "Long-grain basmati rice.",
                (
                    VerticalVariant("5kg Bag", "RGB-RICE-5KG", {"size": "5kg", "type": "Basmati"}, _d("21"), _d("45"), _d("32")),
                    VerticalVariant("10kg Bag", "RGB-RICE-10KG", {"size": "10kg", "type": "Basmati"}, _d("39"), _d("85"), _d("18")),
                ),
            ),
            VerticalProduct(
                "Oliva Extra Virgin Olive Oil",
                "OEV",
                "Oliva",
                "Cooking Oil",
                "Extra virgin olive oil.",
                (
                    VerticalVariant("500ml Bottle", "OEV-OIL-500ML", {"size": "500ml"}, _d("18"), _d("42"), _d("22")),
                    VerticalVariant("1L Bottle", "OEV-OIL-1L", {"size": "1L"}, _d("30"), _d("69"), _d("15")),
                ),
            ),
            VerticalProduct(
                "Morning Oats",
                "MOO",
                "Morning",
                "Breakfast",
                "Rolled oats for breakfast.",
                (
                    VerticalVariant("1kg Pack", "MOO-OATS-1KG", {"size": "1kg"}, _d("9"), _d("24"), _d("28")),
                    VerticalVariant("2kg Pack", "MOO-OATS-2KG", {"size": "2kg"}, _d("16"), _d("42"), _d("18")),
                ),
            ),
            VerticalProduct(
                "DateBox Premium Dates",
                "DBD",
                "DateBox",
                "Dates",
                "Premium assorted dates.",
                (
                    VerticalVariant("500g Box", "DBD-DATES-500G", {"size": "500g"}, _d("19"), _d("49"), _d("20")),
                    VerticalVariant("1kg Box", "DBD-DATES-1KG", {"size": "1kg"}, _d("33"), _d("79"), _d("14")),
                ),
            ),
        ),
        customers=(
            VerticalCustomer("DEMO-GROC-RAFI", "Rafi Ahmed", "rafi.grocery.demo@example.com", "+971505555001", "Deira", "Often buys rice and pantry bundles."),
            VerticalCustomer("DEMO-GROC-SANA", "Sana Iqbal", "sana.grocery.demo@example.com", "+971505555002", "Ajman", "Buys breakfast items."),
        ),
        orders=(
            VerticalOrder("SO-DEMO-GROCERY-0001", "DEMO-GROC-RAFI", 5, "paid", _d("154"), (("RGB-RICE-10KG", _d("1")), ("OEV-OIL-1L", _d("1")))),
            VerticalOrder("SO-DEMO-GROCERY-0002", "DEMO-GROC-SANA", 2, "paid", _d("66"), (("MOO-OATS-1KG", _d("1")), ("DBD-DATES-500G", _d("1")))),
        ),
    ),
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


def _quantity(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"))


def _minimum_price(price: Decimal) -> Decimal:
    discount = max(Decimal("5"), (price * Decimal("0.08")).quantize(Decimal("0.01")))
    return max(Decimal("0"), price - discount).quantize(Decimal("0.01"))


def _get_or_create_tenant(session: Session, spec: VerticalDemoSpec, owner_password: str | None) -> tuple[ClientModel, UserModel, bool]:
    user = session.execute(
        select(UserModel).where(func.lower(UserModel.email) == spec.tenant_email.lower())
    ).scalar_one_or_none()
    if user is not None:
        client = session.execute(select(ClientModel).where(ClientModel.client_id == user.client_id)).scalar_one()
        return client, user, False

    if not owner_password:
        raise RuntimeError(
            f"Demo tenant {spec.tenant_email} does not exist. Set DEMO_TENANT_PASSWORD or pass --owner-password."
        )

    timestamp = now_utc()
    client_id = new_uuid()
    client = ClientModel(
        client_id=client_id,
        slug=generate_unique_client_code(session, spec.business_name),
        business_name=spec.business_name,
        contact_name=spec.owner_name,
        owner_name=spec.owner_name,
        phone=spec.contact_phone,
        email=spec.tenant_email,
        address="Demo tenant address",
        currency_code=spec.currency_code,
        currency_symbol=spec.currency_symbol,
        timezone=spec.timezone,
        website_url=spec.website_url,
        instagram_url=spec.instagram_url,
        whatsapp_number=spec.whatsapp_number,
        status="active",
        notes=f"{DEMO_REFERENCE_PREFIX} managed demo tenant for {spec.business_type}.",
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(client)
    session.add(
        ClientSettingsModel(
            client_settings_id=new_uuid(),
            client_id=client_id,
            default_location_name=spec.location_name,
            created_at=timestamp,
            updated_at=timestamp,
        )
    )
    user_id = new_uuid()
    user = UserModel(
        user_id=user_id,
        user_code=generate_unique_user_code(session, client.slug, "CLIENT_OWNER", spec.owner_name),
        client_id=client_id,
        name=spec.owner_name,
        email=spec.tenant_email,
        password="",
        password_hash=hash_password(owner_password),
        is_active=True,
        invited_at=None,
        created_at=timestamp,
        updated_at=timestamp,
    )
    session.add(user)
    session.add(UserRoleModel(user_id=user_id, role_code="CLIENT_OWNER"))
    session.flush()
    return client, user, True


def _upsert_location(session: Session, client_id: str, spec: VerticalDemoSpec) -> LocationModel:
    location = session.execute(
        select(LocationModel)
        .where(LocationModel.client_id == client_id, LocationModel.status == "active")
        .order_by(LocationModel.is_default.desc(), LocationModel.created_at.asc())
    ).scalars().first()
    if location is None:
        location = LocationModel(
            location_id=new_uuid(),
            client_id=client_id,
            name=spec.location_name,
            code="DEMO",
            is_default=True,
            status="active",
        )
        session.add(location)
    location.name = spec.location_name
    location.code = location.code or "DEMO"
    location.is_default = True
    location.status = "active"
    session.flush()
    return location


def _upsert_supplier(session: Session, client_id: str, spec: VerticalDemoSpec) -> SupplierModel:
    supplier = session.execute(
        select(SupplierModel).where(SupplierModel.client_id == client_id, SupplierModel.code == spec.supplier_code)
    ).scalar_one_or_none()
    if supplier is None:
        supplier = SupplierModel(supplier_id=new_uuid(), client_id=client_id, code=spec.supplier_code)
        session.add(supplier)
    supplier.name = spec.supplier_name
    supplier.contact_name = "Demo Supply Team"
    supplier.email = f"supply-{spec.business_type}@demo.example"
    supplier.phone = spec.contact_phone
    supplier.address = "Demo supplier address"
    supplier.status = "active"
    supplier.notes = f"{DEMO_REFERENCE_PREFIX} supplier"
    session.flush()
    return supplier


def _upsert_category(session: Session, client_id: str, name: str) -> CategoryModel:
    slug = slugify_identifier(name, max_length=128, default="category")
    category = session.execute(
        select(CategoryModel).where(CategoryModel.client_id == client_id, CategoryModel.slug == slug)
    ).scalar_one_or_none()
    if category is None:
        category = CategoryModel(category_id=new_uuid(), client_id=client_id, name=name, slug=slug)
        session.add(category)
    category.name = name
    category.status = "active"
    category.notes = f"{DEMO_REFERENCE_PREFIX} category"
    session.flush()
    return category


def _upsert_product(
    session: Session,
    *,
    client_id: str,
    supplier: SupplierModel,
    category_by_name: dict[str, CategoryModel],
    product_data: VerticalProduct,
) -> ProductModel:
    slug = slugify_identifier(product_data.name, max_length=128, default="demo-product")
    product = session.execute(
        select(ProductModel).where(ProductModel.client_id == client_id, ProductModel.slug == slug)
    ).scalar_one_or_none()
    if product is None:
        product = ProductModel(product_id=new_uuid(), client_id=client_id, slug=slug)
        session.add(product)
    default_price = min(variant.price for variant in product_data.variants)
    product.supplier_id = supplier.supplier_id
    product.category_id = category_by_name[product_data.category].category_id
    product.name = product_data.name
    product.sku_root = product_data.sku_root
    product.brand = product_data.brand
    product.description = product_data.description
    product.status = "active"
    product.default_price_amount = _money(default_price)
    product.min_price_amount = _minimum_price(default_price)
    product.max_discount_percent = product_data.max_discount_percent
    session.flush()
    return product


def _upsert_variant(
    session: Session,
    *,
    client_id: str,
    product: ProductModel,
    variant_data: VerticalVariant,
) -> ProductVariantModel:
    variant = session.execute(
        select(ProductVariantModel).where(
            ProductVariantModel.client_id == client_id,
            ProductVariantModel.sku == variant_data.sku,
        )
    ).scalar_one_or_none()
    if variant is None:
        variant = ProductVariantModel(
            variant_id=new_uuid(),
            client_id=client_id,
            product_id=product.product_id,
            sku=variant_data.sku,
        )
        session.add(variant)
    variant.product_id = product.product_id
    variant.title = variant_data.title
    variant.option_values_json = variant_data.options
    variant.status = "active"
    variant.cost_amount = _money(variant_data.cost)
    variant.price_amount = _money(variant_data.price)
    variant.min_price_amount = _minimum_price(variant_data.price)
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
    reference_id: str,
    created_by_user_id: str,
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
            reference_id=reference_id,
            reference_line_id=variant.sku,
            quantity_delta=delta,
            unit_cost_amount=variant.cost_amount,
            unit_price_amount=variant.price_amount,
            reason=f"Set {reference_id} stock target",
            created_by_user_id=created_by_user_id,
        )
    )
    return True


def _upsert_customers(session: Session, client_id: str, customers: tuple[VerticalCustomer, ...]) -> dict[str, CustomerModel]:
    records: dict[str, CustomerModel] = {}
    for payload in customers:
        customer = session.execute(
            select(CustomerModel).where(CustomerModel.client_id == client_id, CustomerModel.code == payload.code)
        ).scalar_one_or_none()
        if customer is None:
            customer = CustomerModel(customer_id=new_uuid(), client_id=client_id, code=payload.code)
            session.add(customer)
        customer.name = payload.name
        customer.email = payload.email
        customer.email_normalized = normalize_email(payload.email)
        customer.phone = payload.phone
        customer.phone_normalized = normalize_phone(payload.phone)
        customer.whatsapp_number = normalize_phone(payload.phone)
        customer.address = payload.address
        customer.status = "active"
        customer.notes = payload.notes
        records[payload.code] = customer
    session.flush()
    return records


def _create_demo_orders(
    session: Session,
    *,
    client_id: str,
    location: LocationModel,
    customers: dict[str, CustomerModel],
    variants_by_sku: dict[str, ProductVariantModel],
    orders: tuple[VerticalOrder, ...],
    created_by_user_id: str,
) -> int:
    created = 0
    now = datetime.now(UTC)
    for payload in orders:
        exists = session.execute(
            select(SalesOrderModel.sales_order_id).where(
                SalesOrderModel.client_id == client_id,
                SalesOrderModel.order_number == payload.order_number,
            )
        ).scalar_one_or_none()
        if exists is not None:
            continue
        order = SalesOrderModel(
            sales_order_id=new_uuid(),
            client_id=client_id,
            customer_id=customers[payload.customer_code].customer_id,
            location_id=location.location_id,
            order_number=payload.order_number,
            status="completed",
            payment_status=payload.payment_status,
            shipment_status="fulfilled",
            ordered_at=now - timedelta(days=payload.days_ago),
            confirmed_at=now - timedelta(days=payload.days_ago),
            notes=f"{DEMO_REFERENCE_PREFIX} fulfilled demo order",
            created_by_user_id=created_by_user_id,
            source_type="manual",
            subtotal_amount=ZERO,
            discount_amount=ZERO,
            total_amount=ZERO,
            paid_amount=_money(payload.paid_amount),
        )
        session.add(order)
        session.flush()
        total = ZERO
        for sku, quantity in payload.lines:
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
                    reason=f"{DEMO_REFERENCE_PREFIX} fulfilled sale",
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
                amount=_money(payload.paid_amount),
                paid_at=order.confirmed_at,
                reference=f"PAY-{payload.order_number}",
                notes=f"{DEMO_REFERENCE_PREFIX} payment",
                created_by_user_id=created_by_user_id,
            )
        )
        created += 1
    return created


def _upsert_playbook(session: Session, client_id: str, spec: VerticalDemoSpec) -> None:
    playbook = session.execute(
        select(AssistantPlaybookModel).where(AssistantPlaybookModel.client_id == client_id)
    ).scalar_one_or_none()
    if playbook is None:
        playbook = AssistantPlaybookModel(playbook_id=new_uuid(), client_id=client_id)
        session.add(playbook)
    playbook.status = "active"
    playbook.business_type = spec.business_type
    playbook.brand_personality = spec.brand_personality
    playbook.custom_instructions = spec.custom_instructions
    playbook.forbidden_claims = spec.forbidden_claims
    playbook.sales_goals_json = {
        "upsell": True,
        "cross_sell": True,
        "promote_slow_stock": True,
        "protect_premium_positioning": spec.brand_personality in {"premium", "expert"},
    }
    playbook.policy_json = spec.policies
    playbook.escalation_rules_json = {**DEFAULT_ESCALATION_RULES}
    playbook.industry_template_json = INDUSTRY_TEMPLATES.get(spec.business_type, INDUSTRY_TEMPLATES["general_retail"])


def _upsert_channel(
    session: Session,
    *,
    client_id: str,
    spec: VerticalDemoSpec,
    location: LocationModel,
    created_by_user_id: str,
) -> CustomerChannelModel:
    external_account_id = f"demo-{spec.business_type}-website"
    channel = session.execute(
        select(CustomerChannelModel).where(
            CustomerChannelModel.client_id == client_id,
            CustomerChannelModel.provider == "website",
            CustomerChannelModel.external_account_id == external_account_id,
        )
    ).scalar_one_or_none()
    if channel is None:
        channel = CustomerChannelModel(
            channel_id=new_uuid(),
            client_id=client_id,
            provider="website",
            external_account_id=external_account_id,
            webhook_key=f"cc_{new_uuid().replace('-', '')}",
            created_by_user_id=created_by_user_id,
        )
        session.add(channel)
    channel.display_name = f"{spec.business_name} Website"
    channel.status = "active"
    channel.default_location_id = location.location_id
    channel.auto_send_enabled = True
    channel.config_json = {"demo_vertical": spec.business_type, "source": DEMO_REFERENCE_PREFIX}
    session.flush()
    return channel


def _clean_demo_conversations(session: Session, client_id: str, spec: VerticalDemoSpec) -> int:
    pattern = f"{DEMO_SENDER_PREFIX}{spec.business_type}-%"
    count = int(
        session.execute(
            select(func.count()).select_from(CustomerConversationModel).where(
                CustomerConversationModel.client_id == client_id,
                CustomerConversationModel.external_sender_id.like(pattern),
            )
        ).scalar_one()
        or 0
    )
    session.execute(
        delete(CustomerConversationModel).where(
            CustomerConversationModel.client_id == client_id,
            CustomerConversationModel.external_sender_id.like(pattern),
        )
    )
    return count


def _update_client_profile(client: ClientModel, spec: VerticalDemoSpec) -> None:
    client.business_name = spec.business_name
    client.contact_name = spec.owner_name
    client.owner_name = spec.owner_name
    client.phone = spec.contact_phone
    client.email = spec.tenant_email
    client.currency_code = spec.currency_code
    client.currency_symbol = spec.currency_symbol
    client.timezone = spec.timezone
    client.website_url = spec.website_url
    client.instagram_url = spec.instagram_url
    client.whatsapp_number = spec.whatsapp_number
    client.status = "active"
    client.notes = f"{DEMO_REFERENCE_PREFIX} managed demo tenant for {spec.business_type}."


def backfill_vertical_demo_tenants(
    *,
    tenant_emails: set[str] | None,
    owner_password: str | None,
    apply: bool,
) -> list[dict[str, Any]]:
    engine = build_postgres_engine(settings)
    SessionFactory = build_session_factory(engine)
    selected_specs = [
        spec for spec in DEMO_SPECS if tenant_emails is None or spec.tenant_email.lower() in tenant_emails
    ]
    summaries: list[dict[str, Any]] = []
    with SessionFactory() as session:
        for spec in selected_specs:
            client, user, tenant_created = _get_or_create_tenant(session, spec, owner_password)
            client_id = str(client.client_id)
            _update_client_profile(client, spec)
            location = _upsert_location(session, client_id, spec)
            supplier = _upsert_supplier(session, client_id, spec)
            categories = {
                name: _upsert_category(session, client_id, name)
                for name in sorted({product.category for product in spec.products})
            }
            variants_by_sku: dict[str, ProductVariantModel] = {}
            products_upserted = 0
            variants_upserted = 0
            stock_adjustments = 0
            for product_data in spec.products:
                product = _upsert_product(
                    session,
                    client_id=client_id,
                    supplier=supplier,
                    category_by_name=categories,
                    product_data=product_data,
                )
                products_upserted += 1
                for variant_data in product_data.variants:
                    variant = _upsert_variant(
                        session,
                        client_id=client_id,
                        product=product,
                        variant_data=variant_data,
                    )
                    variants_by_sku[variant.sku] = variant
                    variants_upserted += 1
            customers = _upsert_customers(session, client_id, spec.customers)
            orders_created = _create_demo_orders(
                session,
                client_id=client_id,
                location=location,
                customers=customers,
                variants_by_sku=variants_by_sku,
                orders=spec.orders,
                created_by_user_id=str(user.user_id),
            )
            session.flush()
            reference_id = f"{DEMO_REFERENCE_PREFIX}-{spec.business_type.upper()}"
            for product_data in spec.products:
                for variant_data in product_data.variants:
                    if _set_stock_target(
                        session,
                        client_id=client_id,
                        variant=variants_by_sku[variant_data.sku],
                        location=location,
                        target_stock=variant_data.target_stock,
                        reference_id=reference_id,
                        created_by_user_id=str(user.user_id),
                    ):
                        stock_adjustments += 1
            _upsert_playbook(session, client_id, spec)
            channel = _upsert_channel(
                session,
                client_id=client_id,
                spec=spec,
                location=location,
                created_by_user_id=str(user.user_id),
            )
            cleaned_conversations = _clean_demo_conversations(session, client_id, spec)
            summaries.append(
                {
                    "tenant_email": spec.tenant_email,
                    "client_id": client_id,
                    "business_name": spec.business_name,
                    "business_type": spec.business_type,
                    "tenant_created": tenant_created,
                    "products": products_upserted,
                    "variants": variants_upserted,
                    "stock_adjustments": stock_adjustments,
                    "customers": len(customers),
                    "orders_created": orders_created,
                    "cleaned_demo_conversations": cleaned_conversations,
                    "channel_display_name": channel.display_name,
                    "channel_key": channel.webhook_key,
                }
            )
        if apply:
            session.commit()
        else:
            session.rollback()
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill reusable vertical demo tenants.")
    parser.add_argument("--tenant-email", action="append", help="Limit to one tenant email. May be repeated.")
    parser.add_argument("--owner-password", default=os.getenv("DEMO_TENANT_PASSWORD", ""), help="Password used only when creating missing demo owner users.")
    parser.add_argument("--apply", action="store_true", help="Commit the backfill. Without this flag, changes are rolled back.")
    args = parser.parse_args()

    tenant_emails = {email.strip().lower() for email in args.tenant_email or [] if email.strip()} or None
    summaries = backfill_vertical_demo_tenants(
        tenant_emails=tenant_emails,
        owner_password=args.owner_password or None,
        apply=args.apply,
    )
    mode = "applied" if args.apply else "dry_run"
    print(f"[vertical-demo] mode={mode}")
    for summary in summaries:
        print(f"[vertical-demo] tenant_email={summary['tenant_email']}")
        for key, value in summary.items():
            if key == "tenant_email":
                continue
            print(f"[vertical-demo] {key}={value}")


if __name__ == "__main__":
    main()
