import type { ProductRecord, ProductsStockSnapshot, SaveProductPayload } from '@/types/products-stock';

const MOCK_PRODUCTS: ProductRecord[] = [
  {
    id: 'p-100',
    identity: {
      productName: 'Urban Fit Tee',
      supplier: 'Nova Textiles',
      category: 'Apparel',
      description: 'Premium cotton crew-neck t-shirt.',
      features: ['180 GSM', 'Bio-washed', 'Regular fit']
    },
    variants: [
      {
        rowId: 'row-v-1001',
        variant_id: 'v-1001',
        size: 'S',
        color: 'Black',
        other: '',
        qty: 42,
        cost: 8.75,
        defaultSellingPrice: 16.5,
        maxDiscountPct: 10
      },
      {
        rowId: 'row-v-1002',
        variant_id: 'v-1002',
        size: 'M',
        color: 'White',
        other: '',
        qty: 33,
        cost: 8.75,
        defaultSellingPrice: 16.5,
        maxDiscountPct: 10
      }
    ]
  },
  {
    id: 'p-200',
    identity: {
      productName: 'Aero Flask 750ml',
      supplier: 'HydroWorks',
      category: 'Lifestyle',
      description: 'Double-wall steel hydration bottle.',
      features: ['Leak-proof lid', 'BPA free']
    },
    variants: [
      {
        rowId: 'row-v-2001',
        variant_id: 'v-2001',
        size: '',
        color: 'Navy',
        other: 'Matte',
        qty: 18,
        cost: 6.3,
        defaultSellingPrice: 14,
        maxDiscountPct: 10
      }
    ]
  }
];

const MOCK_SUPPLIERS = ['Nova Textiles', 'HydroWorks', 'Peak Source'];
const MOCK_CATEGORIES = ['Apparel', 'Lifestyle', 'Accessories'];

export async function getProductsStockSnapshot(): Promise<ProductsStockSnapshot> {
  return {
    products: structuredClone(MOCK_PRODUCTS),
    suppliers: [...MOCK_SUPPLIERS],
    categories: [...MOCK_CATEGORIES]
  };
}

export async function saveProductStock(payload: SaveProductPayload): Promise<{ success: true }> {
  void payload;
  return { success: true };
}
