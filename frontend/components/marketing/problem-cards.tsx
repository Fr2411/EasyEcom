type ProblemCardItem = {
  title: string;
  body: string;
};

export function ProblemCards({ items }: { items: ProblemCardItem[] }) {
  return (
    <div className="landing-problem-grid">
      {items.map((problem, index) => (
        <article key={problem.title} className="landing-problem-card">
          <span className="landing-card-number">0{index + 1}</span>
          <h3>{problem.title}</h3>
          <p>{problem.body}</p>
        </article>
      ))}
    </div>
  );
}
