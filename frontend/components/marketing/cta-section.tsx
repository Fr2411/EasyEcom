import type { ReactNode } from 'react';

export function CTASection({
  title,
  description,
  actions,
}: {
  title: string;
  description: string;
  actions: ReactNode;
}) {
  return (
    <section className="marketing-section landing-section">
      <div className="landing-final-cta">
        <div>
          <p className="marketing-kicker">Start today</p>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <div className="landing-cta-row">{actions}</div>
      </div>
    </section>
  );
}
