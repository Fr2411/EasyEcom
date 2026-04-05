import type { ReactNode } from 'react';

export function HeroSection({
  title,
  description,
  actions,
  trustLine,
  visual,
}: {
  title: string;
  description: string;
  actions: ReactNode;
  trustLine: string;
  visual: ReactNode;
}) {
  return (
    <section className="marketing-hero landing-hero">
      <div className="landing-hero-grid">
        <div className="landing-copy">
          <div className="landing-hero-badges" aria-label="EasyEcom highlights">
            <span>AI sales</span>
            <span>Realtime inventory</span>
            <span>Ops control</span>
          </div>
          <h1>{title}</h1>
          <p className="landing-subheadline">{description}</p>
          <div className="landing-cta-row">{actions}</div>
          <p className="landing-trust-line">{trustLine}</p>
        </div>
        {visual}
      </div>
    </section>
  );
}
