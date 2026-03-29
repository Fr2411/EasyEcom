type PricingPreviewPlan = {
  title: string;
  body: string;
  points: string[];
};

export function PricingPreview({ plans }: { plans: PricingPreviewPlan[] }) {
  return (
    <div className="landing-pricing-grid">
      {plans.map((plan) => (
        <article key={plan.title} className="landing-pricing-card">
          <h3>{plan.title}</h3>
          <p>{plan.body}</p>
          <ul>
            {plan.points.map((point) => (
              <li key={point}>{point}</li>
            ))}
          </ul>
        </article>
      ))}
    </div>
  );
}
