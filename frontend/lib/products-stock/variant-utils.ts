import type { Variant } from '@/types/products-stock';

const DEFAULT_DISCOUNT = 10;

function parseCsvValues(value: string): string[] {
  return value
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

export function generateVariantsFromInputs(sizeInput: string, colorInput: string, otherInput: string): Variant[] {
  const sizes = parseCsvValues(sizeInput);
  const colors = parseCsvValues(colorInput);
  const others = parseCsvValues(otherInput);

  const sizeSource = sizes.length ? sizes : [''];
  const colorSource = colors.length ? colors : [''];
  const otherSource = others.length ? others : [''];

  const variants: Variant[] = [];

  sizeSource.forEach((size) => {
    colorSource.forEach((color) => {
      otherSource.forEach((other) => {
        const label = [size, color, other].filter(Boolean).join(' / ') || 'Standard';
        variants.push({
          id: `new-${label}-${Math.random().toString(36).slice(2, 9)}`,
          label,
          size: size || undefined,
          color: color || undefined,
          other: other || undefined,
          qty: 0,
          cost: 0,
          defaultSellingPrice: 0,
          maxDiscountPct: DEFAULT_DISCOUNT
        });
      });
    });
  });

  return variants;
}

export function toFeatureList(input: string): string[] {
  return input
    .split(',')
    .map((feature) => feature.trim())
    .filter(Boolean);
}

export function featureListToInput(features: string[]): string {
  return features.join(', ');
}

export function createEmptyVariant(): Variant {
  return {
    id: `manual-${Math.random().toString(36).slice(2, 9)}`,
    label: '',
    qty: 0,
    cost: 0,
    defaultSellingPrice: 0,
    maxDiscountPct: DEFAULT_DISCOUNT
  };
}

export function summarizeVariants(variants: Variant[]): {
  variantCount: number;
  totalQty: number;
  estimatedStockCost: number;
} {
  const totalQty = variants.reduce((sum, variant) => sum + (Number(variant.qty) || 0), 0);
  const estimatedStockCost = variants.reduce(
    (sum, variant) => sum + (Number(variant.qty) || 0) * (Number(variant.cost) || 0),
    0
  );

  return {
    variantCount: variants.length,
    totalQty,
    estimatedStockCost
  };
}
