from pydantic import BaseModel, Field


class ProductIdentity(BaseModel):
    productName: str = Field(min_length=1)
    supplier: str = ""
    category: str = "General"
    description: str = ""
    features: list[str] = []


class VariantRecord(BaseModel):
    id: str = ""
    label: str = ""
    qty: float = 0.0
    cost: float = 0.0
    defaultSellingPrice: float = 0.0
    maxDiscountPct: float = 10.0
    size: str | None = None
    color: str | None = None
    other: str | None = None


class ProductRecord(BaseModel):
    id: str
    identity: ProductIdentity
    variants: list[VariantRecord]


class ProductsStockSnapshotResponse(BaseModel):
    products: list[ProductRecord]
    suppliers: list[str]
    categories: list[str]


class SaveProductsStockRequest(BaseModel):
    mode: str = "new"
    identity: ProductIdentity
    variants: list[VariantRecord]
    selectedProductId: str | None = None


class SaveProductResponse(BaseModel):
    success: bool = True
