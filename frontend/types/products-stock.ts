export type VariantMode = 'existing' | 'new';

export type Variant = {
  id: string;
  label: string;
  qty: number;
  cost: number;
  defaultSellingPrice: number;
  maxDiscountPct: number;
  size?: string;
  color?: string;
  other?: string;
};

export type ProductIdentity = {
  productName: string;
  supplier: string;
  category: string;
  description: string;
  features: string[];
};

export type ProductRecord = {
  id: string;
  identity: ProductIdentity;
  variants: Variant[];
};

export type ProductLookupOption = {
  id: string;
  name: string;
};

export type ProductsStockSnapshot = {
  products: ProductRecord[];
  suppliers: string[];
  categories: string[];
};

export type SaveProductPayload = {
  mode: VariantMode;
  identity: ProductIdentity;
  variants: Variant[];
};
