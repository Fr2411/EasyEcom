export function PageShell({
  title,
  description,
  children
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
}) {
  return (
    <section className="page-shell">
      <header className="page-shell-header">
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      <div className="page-shell-body">{children}</div>
    </section>
  );
}
