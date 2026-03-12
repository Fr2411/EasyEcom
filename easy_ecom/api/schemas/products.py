from pydantic import BaseModel, Field


class ProductSearchItem(BaseModel):
    product_id: str
    product_name: str


class ProductDetailResponse(BaseModel):
    product: dict[str, str | float]
    variants: list[dict[str, str | float]]


class VariantRow(BaseModel):
    variant_id: str = ""
    variant_label: str = ""
    size: str = ""
    color: str = ""
    other: str = ""
    qty: float = 0.0
    unit_cost: float = 0.0
    default_selling_price: float = 0.0
    max_discount_pct: float = 10.0


class ProductUpsertRequest(BaseModel):
    typed_product_name: str = Field(min_length=1)
    supplier: str = ""
    category: str = "General"
    description: str = ""
    features_text: str = ""
    selected_product_id: str = ""
    variant_entries: list[VariantRow]


class ProductUpsertResponse(BaseModel):
    product_id: str
    lot_ids: list[str]
    variant_upserts: int


class StockExplorerResponse(BaseModel):
    summary: list[dict[str, str | float | int]]
    detail: dict[str, list[dict[str, str | float]]]
