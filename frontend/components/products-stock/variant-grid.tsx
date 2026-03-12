'use client';

import type { Variant } from '@/types/products-stock';

type VariantGridProps = {
  variants: Variant[];
  sameCostEnabled: boolean;
  sharedCost: string;
  onSameCostEnabledChange: (enabled: boolean) => void;
  onSharedCostChange: (value: string) => void;
  onApplySharedCost: () => void;
  onVariantChange: (id: string, field: keyof Variant, value: string) => void;
  onAddVariant: () => void;
  onRemoveVariant: (id: string) => void;
};

export function VariantGrid({
  variants,
  sameCostEnabled,
  sharedCost,
  onSameCostEnabledChange,
  onSharedCostChange,
  onApplySharedCost,
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
      <div className="inline-add-row">
        <label>
          <input type="checkbox" checked={sameCostEnabled} onChange={(e) => onSameCostEnabledChange(e.target.checked)} />
          Same cost for all rows
        </label>
        {sameCostEnabled ? (
          <>
            <input value={sharedCost} onChange={(e) => onSharedCostChange(e.target.value)} placeholder="Shared cost" />
            <button type="button" onClick={onApplySharedCost}>Apply</button>
          </>
        ) : null}
      </div>
      <table>
        <thead>
          <tr><th>Size</th><th>Color</th><th>Other</th><th>Qty</th><th>Cost</th><th>Price</th><th>Max Discount %</th><th /></tr>
        </thead>
        <tbody>
          {variants.map((variant) => (
            <tr key={variant.id}>
              <td><input value={variant.size} onChange={(e) => onVariantChange(variant.id, 'size', e.target.value)} /></td>
              <td><input value={variant.color} onChange={(e) => onVariantChange(variant.id, 'color', e.target.value)} /></td>
              <td><input value={variant.other} onChange={(e) => onVariantChange(variant.id, 'other', e.target.value)} /></td>
              <td><input value={String(variant.qty)} onChange={(e) => onVariantChange(variant.id, 'qty', e.target.value)} /></td>
              <td><input value={String(variant.cost)} onChange={(e) => onVariantChange(variant.id, 'cost', e.target.value)} /></td>
              <td><input value={String(variant.defaultSellingPrice)} onChange={(e) => onVariantChange(variant.id, 'defaultSellingPrice', e.target.value)} /></td>
              <td><input value={String(variant.maxDiscountPct)} onChange={(e) => onVariantChange(variant.id, 'maxDiscountPct', e.target.value)} /></td>
              <td><button type="button" onClick={() => onRemoveVariant(variant.id)}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
