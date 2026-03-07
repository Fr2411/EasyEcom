'use client';

import { useState } from 'react';

type VariantGeneratorProps = {
  onGenerate: (inputs: { size: string; color: string; other: string }) => void;
};

export function VariantGenerator({ onGenerate }: VariantGeneratorProps) {
  const [size, setSize] = useState('');
  const [color, setColor] = useState('');
  const [other, setOther] = useState('');

  return (
    <section className="ps-card">
      <div className="ps-headline-row">
        <h3>Generate variants</h3>
      </div>
      <div className="generator-grid">
        <label>
          Size values
          <input value={size} onChange={(e) => setSize(e.target.value)} placeholder="S, M, L" />
        </label>
        <label>
          Color values
          <input value={color} onChange={(e) => setColor(e.target.value)} placeholder="Black, White" />
        </label>
        <label>
          Other values
          <input value={other} onChange={(e) => setOther(e.target.value)} placeholder="Matte, Gloss" />
        </label>
        <button type="button" onClick={() => onGenerate({ size, color, other })}>
          Generate combinations
        </button>
      </div>
    </section>
  );
}
