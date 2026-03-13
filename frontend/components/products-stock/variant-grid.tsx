'use client';

import type { CatalogVariant } from '@/types/catalog';

type VariantGridProps = {
  variants: CatalogVariant[];
  onVariantChange: (tempId: string, field: keyof CatalogVariant, value: string) => void;
  onAddVariant: () => void;
  onToggleArchiveVariant: (tempId: string) => void;
  onRemoveVariant: (tempId: string) => void;
};

export function VariantGrid({
  variants,
  onVariantChange,
  onAddVariant,
  onToggleArchiveVariant,
  onRemoveVariant
}: VariantGridProps) {
  return (
    <section className="ps-card">
      <div className="ps-headline-row">
        <h3>Variant grid</h3>
        <button type="button" onClick={onAddVariant}>Add row</button>
      </div>
      <div className="variant-grid-wrap">
        <table className="variant-grid">
          <thead>
            <tr>
              <th>Size</th>
              <th>Color</th>
              <th>Other</th>
              <th>Purchase Price</th>
              <th>Default Price</th>
              <th>Max Discount %</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {variants.map((variant) => (
              <tr key={variant.tempId} data-archived={variant.isArchived ? 'true' : 'false'}>
                <td>
                  <input
                    value={variant.size}
                    disabled={variant.isArchived}
                    onChange={(e) => onVariantChange(variant.tempId, 'size', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={variant.color}
                    disabled={variant.isArchived}
                    onChange={(e) => onVariantChange(variant.tempId, 'color', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={variant.other}
                    disabled={variant.isArchived}
                    onChange={(e) => onVariantChange(variant.tempId, 'other', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    aria-label={`Purchase Price ${variant.size || variant.color || variant.other || variant.tempId}`}
                    value={String(variant.defaultPurchasePrice)}
                    disabled={variant.isArchived}
                    onChange={(e) => onVariantChange(variant.tempId, 'defaultPurchasePrice', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={String(variant.defaultSellingPrice)}
                    disabled={variant.isArchived}
                    onChange={(e) => onVariantChange(variant.tempId, 'defaultSellingPrice', e.target.value)}
                  />
                </td>
                <td>
                  <input
                    value={String(variant.maxDiscountPct)}
                    disabled={variant.isArchived}
                    onChange={(e) => onVariantChange(variant.tempId, 'maxDiscountPct', e.target.value)}
                  />
                </td>
                <td>{variant.isArchived ? 'Archived on save' : 'Active'}</td>
                <td>
                  {variant.variant_id ? (
                    <button type="button" onClick={() => onToggleArchiveVariant(variant.tempId)}>
                      {variant.isArchived ? 'Keep active' : 'Archive'}
                    </button>
                  ) : (
                    <button type="button" onClick={() => onRemoveVariant(variant.tempId)}>Remove</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
