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

const columns: Array<{ key: keyof Variant | 'remove'; label: string }> = [
  { key: 'label', label: 'Variant label' },
  { key: 'qty', label: 'Qty' },
  { key: 'cost', label: 'Cost' },
  { key: 'defaultSellingPrice', label: 'Default Selling Price' },
  { key: 'maxDiscountPct', label: 'Max Discount %' },
  { key: 'remove', label: '' }
];

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
        <h3>Variants</h3>
        <button type="button" onClick={onAddVariant}>
          + Add variant
        </button>
      </div>

      <div className="same-cost-row">
        <label>
          <input
            type="checkbox"
            checked={sameCostEnabled}
            onChange={(e) => onSameCostEnabledChange(e.target.checked)}
          />
          Same cost for all variants
        </label>
        {sameCostEnabled ? (
          <>
            <input
              type="number"
              step="0.01"
              value={sharedCost}
              onChange={(e) => onSharedCostChange(e.target.value)}
              placeholder="Shared cost"
              aria-label="Shared cost"
            />
            <button type="button" onClick={onApplySharedCost}>
              Apply shared cost
            </button>
          </>
        ) : null}
      </div>

      <div className="variant-grid-wrap">
        <table className="variant-grid">
          <thead>
            <tr>
              {columns.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {variants.map((variant) => (
              <tr key={variant.id}>
                <td>
                  <input
                    value={variant.label}
                    onChange={(e) => onVariantChange(variant.id, 'label', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={variant.qty}
                    onChange={(e) => onVariantChange(variant.id, 'qty', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="0.01"
                    value={variant.cost}
                    onChange={(e) => onVariantChange(variant.id, 'cost', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    step="0.01"
                    value={variant.defaultSellingPrice}
                    onChange={(e) => onVariantChange(variant.id, 'defaultSellingPrice', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={variant.maxDiscountPct}
                    onChange={(e) => onVariantChange(variant.id, 'maxDiscountPct', e.target.value)}
                  />
                </td>
                <td>
                  <button type="button" onClick={() => onRemoveVariant(variant.id)} aria-label={`Remove ${variant.label}`}>
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
