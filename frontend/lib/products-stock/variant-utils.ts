import type { Variant, VariantGenerationInput } from '@/types/products-stock';

const DEFAULT_DISCOUNT = 10;

const parseCsvValues = (value: string): string[] => {
  const deduped = new Map<string, string>();

  value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean)
    .forEach((part) => {
      const normalizedKey = part.toLowerCase();
      if (!deduped.has(normalizedKey)) {
        deduped.set(normalizedKey, part);
      }
    });

  return Array.from(deduped.values());
};

export function variantIdentityKey(variant: Variant): string {
  return [variant.size, variant.color, variant.other].map((v) => v.trim().toLowerCase()).join('|');
}

export function hasIdentity(variant: Variant): boolean {
  return [variant.size, variant.color, variant.other].some((v) => v.trim().length > 0);
}

export function generateVariantsFromInputs({ size, color, other }: VariantGenerationInput): Variant[] {
  const sizes = parseCsvValues(size);
  const colors = parseCsvValues(color);
  const others = parseCsvValues(other);

  const sizeSource = sizes.length ? sizes : [''];
  const colorSource = colors.length ? colors : [''];
  const otherSource = others.length ? others : [''];

  const rows: Variant[] = [];
  sizeSource.forEach((s) => {
    colorSource.forEach((c) => {
      otherSource.forEach((o) => {
        rows.push({
          rowId: crypto.randomUUID(),
          variant_id: crypto.randomUUID(),
          size: s,
          color: c,
          other: o,
          qty: 0,
          cost: 0,
          defaultSellingPrice: 0,
          maxDiscountPct: DEFAULT_DISCOUNT
        });
      });
    });
  });
  return rows;
}

export const toFeatureList = (input: string): string[] =>
  input
    .split(',')
    .map((feature) => feature.trim())
    .filter(Boolean);

export const featureListToInput = (features: string[]): string => features.join(', ');

export function createEmptyVariant(): Variant {
  return {
    rowId: crypto.randomUUID(),
    variant_id: crypto.randomUUID(),
    size: '',
    color: '',
    other: '',
    qty: 0,
    cost: 0,
    defaultSellingPrice: 0,
    maxDiscountPct: DEFAULT_DISCOUNT
  };
}

export function summarizeVariants(variants: Variant[]) {
  const totalQty = variants.reduce((sum, v) => sum + (Number(v.qty) || 0), 0);
  const estimatedStockCost = variants.reduce((sum, v) => sum + (Number(v.qty) || 0) * (Number(v.cost) || 0), 0);
  return { variantCount: variants.length, totalQty, estimatedStockCost };
}
