from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    client_id: str
    supplier: str
    product_name: str = Field(min_length=1)
    category: str = "General"
    prd_description: str = ""
    prd_features_json: str = "{}"
    default_selling_price: float = Field(gt=0)
    max_discount_pct: float = Field(ge=0, le=100, default=10.0)
    sizes_csv: str = ""
    colors_csv: str = ""
    others_csv: str = ""


class ProductPricingUpdate(BaseModel):
    default_selling_price: float = Field(gt=0)
    max_discount_pct: float = Field(ge=0, le=100, default=10.0)
