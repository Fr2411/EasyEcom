'use client';

import { useId } from 'react';

export function HoverHint({
  text,
  label = 'More information',
}: {
  text: string;
  label?: string;
}) {
  const hintId = useId();

  return (
    <span className="workspace-hint" tabIndex={0} aria-label={label} aria-describedby={hintId}>
      <span aria-hidden="true">i</span>
      <span id={hintId} role="tooltip" className="workspace-hint-text">
        {text}
      </span>
    </span>
  );
}
