'use client';

import type { CatalogVariant } from '@/types/catalog';

type VariantGridProps = {
  variants: CatalogVariant[];
  onVariantChange: (tempId: string, field: keyof CatalogVariant, value: string) => void;
  onAddVariant: () => void;
  onRemoveVariant: (tempId: string) => void;
};

export function VariantGrid({
  variants,
  onVariantChange,
  onAddVariant,
  onRemoveVariant
}: VariantGridProps) {
  return (
    <section className="ps-card">
      <div className="ps-headline-row">
        <h3>Variant grid</h3>
        <button type="button" onClick={onAddVariant}>Add row</button>
      </div>
      <table>
        <thead>
          <tr><th>Size</th><th>Color</th><th>Other</th><th>Default Price</th><th>Max Discount %</th><th /></tr>
        </thead>
        <tbody>
          {variants.map((variant) => (
            <tr key={variant.tempId}>
              <td><input value={variant.size} onChange={(e) => onVariantChange(variant.tempId, 'size', e.target.value)} /></td>
              <td><input value={variant.color} onChange={(e) => onVariantChange(variant.tempId, 'color', e.target.value)} /></td>
              <td><input value={variant.other} onChange={(e) => onVariantChange(variant.tempId, 'other', e.target.value)} /></td>
              <td><input value={String(variant.defaultSellingPrice)} onChange={(e) => onVariantChange(variant.tempId, 'defaultSellingPrice', e.target.value)} /></td>
              <td><input value={String(variant.maxDiscountPct)} onChange={(e) => onVariantChange(variant.tempId, 'maxDiscountPct', e.target.value)} /></td>
              <td><button type="button" onClick={() => onRemoveVariant(variant.tempId)}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
