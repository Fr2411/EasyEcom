from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ProductIdentity(BaseModel):
    productName: str = Field(min_length=1)
    supplier: str = ""
    category: str = "General"
    description: str = ""
    features: list[str] = Field(default_factory=list)


class VariantRecord(BaseModel):
    id: str = ""
    size: str = ""
    color: str = ""
    other: str = ""
    qty: float = 0.0
    cost: float = 0.0
    defaultPurchasePrice: float = 0.0
    defaultSellingPrice: float = 0.0
    maxDiscountPct: float = 10.0

    @property
    def identity_key(self) -> str:
        def norm(value: str) -> str:
            return str(value or "").strip().lower()

        return f"{norm(self.size)}|{norm(self.color)}|{norm(self.other)}"

    @property
    def has_identity(self) -> bool:
        return any(str(value or "").strip() for value in (self.size, self.color, self.other))


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
    archiveVariantIds: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_variants(self) -> "SaveProductsStockRequest":
        if not self.variants:
            raise ValueError("At least one variant is required")

        seen: set[str] = set()
        for index, variant in enumerate(self.variants, start=1):
            if not variant.has_identity:
                raise ValueError(f"Variant row {index} must include at least one identity field (size/color/other)")
            key = variant.identity_key
            if key in seen:
                raise ValueError("Duplicate variant identity in request: each size/color/other combination must be unique")
            seen.add(key)

        return self


class SaveProductResponse(BaseModel):
    success: bool = True
