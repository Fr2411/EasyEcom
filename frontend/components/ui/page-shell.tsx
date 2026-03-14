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
        <div>
          <h2>{title}</h2>
          <p>{description}</p>
        </div>
        <span className="page-shell-chip">Pilot Workspace</span>
      </header>
      <div className="page-shell-body">{children}</div>
    </section>
  );
}
