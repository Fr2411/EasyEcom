from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class CatalogProductIdentity(BaseModel):
    productName: str = Field(min_length=1)
    supplier: str = ""
    category: str = "General"
    description: str = ""
    features: list[str] = Field(default_factory=list)


class CatalogVariantRecord(BaseModel):
    variant_id: str = ""
    size: str = ""
    color: str = ""
    other: str = ""
    defaultSellingPrice: float = 0.0
    maxDiscountPct: float = 10.0

    @property
    def identity_key(self) -> str:
        return "|".join(
            str(value or "").strip().lower()
            for value in (self.size, self.color, self.other)
        )

    @property
    def has_identity(self) -> bool:
        return any(str(value or "").strip() for value in (self.size, self.color, self.other))


class CatalogProductRecord(BaseModel):
    product_id: str
    identity: CatalogProductIdentity
    variants: list[CatalogVariantRecord]


class CatalogProductsResponse(BaseModel):
    products: list[CatalogProductRecord]
    suppliers: list[str]
    categories: list[str]


class CatalogProductRequest(BaseModel):
    identity: CatalogProductIdentity
    variants: list[CatalogVariantRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_variants(self) -> "CatalogProductRequest":
        seen: set[str] = set()
        for index, variant in enumerate(self.variants, start=1):
            if not variant.has_identity:
                raise ValueError(
                    f"Variant row {index} must include at least one identity field (size/color/other)"
                )
            if variant.defaultSellingPrice < 0:
                raise ValueError(f"Variant row {index} defaultSellingPrice must be >= 0")
            if variant.maxDiscountPct < 0 or variant.maxDiscountPct > 100:
                raise ValueError(f"Variant row {index} maxDiscountPct must be between 0 and 100")
            key = variant.identity_key
            if key in seen:
                raise ValueError("Duplicate variant identity in request")
            seen.add(key)
        return self


class CatalogSaveResponse(BaseModel):
    product_id: str
    variant_count: int
