import type { CatalogVariant, VariantGenerationInput } from '@/types/catalog';

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

export function variantIdentityKey(variant: CatalogVariant): string {
  return [variant.size, variant.color, variant.other].map((v) => v.trim().toLowerCase()).join('|');
}

export function hasIdentity(variant: CatalogVariant): boolean {
  return [variant.size, variant.color, variant.other].some((v) => v.trim().length > 0);
}

export function generateVariantsFromInputs({ size, color, other }: VariantGenerationInput): CatalogVariant[] {
  const sizes = parseCsvValues(size);
  const colors = parseCsvValues(color);
  const others = parseCsvValues(other);

  const sizeSource = sizes.length ? sizes : [''];
  const colorSource = colors.length ? colors : [''];
  const otherSource = others.length ? others : [''];

  const rows: CatalogVariant[] = [];
  sizeSource.forEach((s) => {
    colorSource.forEach((c) => {
      otherSource.forEach((o) => {
        rows.push({
          tempId: crypto.randomUUID(),
          size: s,
          color: c,
          other: o,
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

export function createEmptyVariant(): CatalogVariant {
  return {
    tempId: crypto.randomUUID(),
    size: '',
    color: '',
    other: '',
    defaultSellingPrice: 0,
    maxDiscountPct: DEFAULT_DISCOUNT
  };
}

export function summarizeVariants(variants: CatalogVariant[]) {
  const pricedVariants = variants.filter((variant) => Number(variant.defaultSellingPrice) > 0).length;
  return { variantCount: variants.length, pricedVariants };
}
