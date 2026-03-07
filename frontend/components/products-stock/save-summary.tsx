'use client';

type SaveSummaryProps = {
  variantCount: number;
  totalQty: number;
  estimatedStockCost: number;
  isSaving: boolean;
  isSaveDisabled: boolean;
  validationMessage?: string;
  onSave: () => void;
  onReset: () => void;
};

export function SaveSummary({
  variantCount,
  totalQty,
  estimatedStockCost,
  isSaving,
  isSaveDisabled,
  validationMessage,
  onSave,
  onReset
}: SaveSummaryProps) {
  return (
    <section className="save-bar" aria-live="polite">
      <div className="save-summary-items">
        <span>Variants: {variantCount}</span>
        <span>Total Qty: {totalQty}</span>
        <span>Estimated Stock Cost: ${estimatedStockCost.toFixed(2)}</span>
      </div>
      {validationMessage ? <p className="validation-message">{validationMessage}</p> : null}
      <div className="save-actions">
        <button type="button" onClick={onReset} disabled={isSaving}>
          Clear / Reset
        </button>
        <button type="button" onClick={onSave} disabled={isSaveDisabled || isSaving}>
          {isSaving ? 'Saving...' : 'Save'}
        </button>
      </div>
    </section>
  );
}
