export type VariantOptionValues = {
  size: string;
  color: string;
  other: string;
};

export type VariantGeneratorInput = {
  size_values: string;
  color_values: string;
  other_values: string;
};

export function signatureForValues(size: string, color: string, other: string) {
  return [size.trim().toLowerCase(), color.trim().toLowerCase(), other.trim().toLowerCase()].join('|');
}

export function signatureForVariant(variant: VariantOptionValues) {
  return signatureForValues(variant.size, variant.color, variant.other);
}

export function parseCsvValues(value: string) {
  const seen = new Set<string>();
  return value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => {
      if (!item) return false;
      const key = item.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
}

export function buildVariantCombinations(generator: VariantGeneratorInput): VariantOptionValues[] {
  const sizes = parseCsvValues(generator.size_values);
  const colors = parseCsvValues(generator.color_values);
  const others = parseCsvValues(generator.other_values);
  const sizeAxis = sizes.length ? sizes : [''];
  const colorAxis = colors.length ? colors : [''];
  const otherAxis = others.length ? others : [''];
  const combinations: VariantOptionValues[] = [];

  sizeAxis.forEach((size) => {
    colorAxis.forEach((color) => {
      otherAxis.forEach((other) => {
        combinations.push({ size, color, other });
      });
    });
  });

  return combinations.length ? combinations : [{ size: '', color: '', other: '' }];
}

function normalizeSkuBase(value: string) {
  return value
    .trim()
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .replace(/-+/g, '-');
}

export function buildSkuPreview(
  productName: string,
  skuRoot: string,
  variant: VariantOptionValues & { variant_id?: string | null; sku?: string | null }
) {
  const persisted = variant.variant_id ? variant.sku?.trim() ?? '' : '';
  if (persisted) return persisted;

  const base = normalizeSkuBase(skuRoot || productName || 'PRODUCT');
  const tokens = [variant.size, variant.color, variant.other]
    .map((value) => normalizeSkuBase(value))
    .filter(Boolean);
  return [base, ...tokens].filter(Boolean).join('-') || 'SKU GENERATED ON SAVE';
}
