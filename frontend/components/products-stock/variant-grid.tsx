'use client';

import type { Variant } from '@/types/products-stock';

type VariantGridProps = {
  variants: Variant[];
  sameCostEnabled: boolean;
  sharedCost: string;
  onSameCostEnabledChange: (enabled: boolean) => void;
  onSharedCostChange: (value: string) => void;
  onApplySharedCost: () => void;
  onVariantChange: (rowId: string, field: keyof Variant, value: string) => void;
  onAddVariant: () => void;
  onRemoveVariant: (rowId: string) => void;
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
            <tr key={variant.rowId}>
              <td><input value={variant.size} onChange={(e) => onVariantChange(variant.rowId, 'size', e.target.value)} /></td>
              <td><input value={variant.color} onChange={(e) => onVariantChange(variant.rowId, 'color', e.target.value)} /></td>
              <td><input value={variant.other} onChange={(e) => onVariantChange(variant.rowId, 'other', e.target.value)} /></td>
              <td><input value={String(variant.qty)} onChange={(e) => onVariantChange(variant.rowId, 'qty', e.target.value)} /></td>
              <td><input value={String(variant.cost)} onChange={(e) => onVariantChange(variant.rowId, 'cost', e.target.value)} /></td>
              <td><input value={String(variant.defaultSellingPrice)} onChange={(e) => onVariantChange(variant.rowId, 'defaultSellingPrice', e.target.value)} /></td>
              <td><input value={String(variant.maxDiscountPct)} onChange={(e) => onVariantChange(variant.rowId, 'maxDiscountPct', e.target.value)} /></td>
              <td><button type="button" onClick={() => onRemoveVariant(variant.rowId)}>Remove</button></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
