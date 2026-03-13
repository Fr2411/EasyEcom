'use client';

type SaveSummaryProps = {
  variantCount: number;
  pricedVariants: number;
  isSaving: boolean;
  isSaveDisabled: boolean;
  validationMessage?: string;
  onSave: () => void;
  onReset: () => void;
};

export function SaveSummary({
  variantCount,
  pricedVariants,
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
        <span>Priced Variants: {pricedVariants}</span>
        <span>Stock comes from opening stock, purchases, or adjustments.</span>
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
