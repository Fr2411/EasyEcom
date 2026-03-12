from pydantic import BaseModel, Field


class ProductCreate(BaseModel):
    client_id: str
    supplier: str
    product_name: str = Field(min_length=1)
    category: str = "General"
    prd_description: str = ""
    prd_features_json: str = "{}"
    sizes_csv: str = ""
    colors_csv: str = ""
    others_csv: str = ""
