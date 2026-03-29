import type { LucideIcon } from 'lucide-react';

type FeatureItem = {
  title: string;
  body: string;
  icon: LucideIcon;
};

export function FeatureGrid({ items }: { items: FeatureItem[] }) {
  return (
    <div className="landing-solution-grid">
      {items.map((solution) => {
        const Icon = solution.icon;
        return (
          <article key={solution.title} className="landing-solution-card">
            <div className="landing-solution-icon">
              <Icon size={20} aria-hidden="true" />
            </div>
            <h3>{solution.title}</h3>
            <p>{solution.body}</p>
          </article>
        );
      })}
    </div>
  );
}
