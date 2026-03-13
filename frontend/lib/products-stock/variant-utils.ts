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
          defaultPurchasePrice: 0,
          defaultSellingPrice: 0,
          maxDiscountPct: DEFAULT_DISCOUNT,
          isArchived: false,
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
    defaultPurchasePrice: 0,
    defaultSellingPrice: 0,
    maxDiscountPct: DEFAULT_DISCOUNT,
    isArchived: false,
  };
}

export function summarizeVariants(variants: CatalogVariant[]) {
  const activeVariants = variants.filter((variant) => !variant.isArchived);
  const archivedVariants = variants.length - activeVariants.length;
  const pricedVariants = activeVariants.filter((variant) => Number(variant.defaultSellingPrice) > 0).length;
  const costedVariants = activeVariants.filter((variant) => Number(variant.defaultPurchasePrice) > 0).length;
  return {
    variantCount: activeVariants.length,
    archivedVariants,
    pricedVariants,
    costedVariants,
  };
}

export function mergeCatalogVariants(
  current: CatalogVariant[],
  incoming: CatalogVariant[],
): CatalogVariant[] {
  const merged = current.filter(
    (variant) => Boolean(variant.variant_id) || Boolean(variant.isArchived) || hasIdentity(variant),
  );
  const existingByIdentity = new Map(
    merged
      .filter((variant) => hasIdentity(variant))
      .map((variant) => [variantIdentityKey(variant), variant.tempId]),
  );

  incoming.forEach((variant) => {
    const key = variantIdentityKey(variant);
    if (!hasIdentity(variant)) return;
    const existingTempId = existingByIdentity.get(key);
    if (!existingTempId) {
      merged.push(variant);
      existingByIdentity.set(key, variant.tempId);
      return;
    }
    const existingIndex = merged.findIndex((row) => row.tempId === existingTempId);
    if (existingIndex === -1) return;
    merged[existingIndex] = {
      ...merged[existingIndex],
      isArchived: false,
      size: merged[existingIndex].size || variant.size,
      color: merged[existingIndex].color || variant.color,
      other: merged[existingIndex].other || variant.other,
    };
  });

  return merged;
}
