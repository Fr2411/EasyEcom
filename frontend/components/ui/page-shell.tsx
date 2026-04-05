import { HoverHint } from '@/components/ui/hover-hint';

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
        <div className="page-shell-copy">
          <span className="page-shell-chip">Workspace</span>
          <h2>
            <span className="workspace-heading">
              {title}
              <HoverHint text={description} label={`${title} page help`} />
            </span>
          </h2>
        </div>
      </header>
      <div className="page-shell-body">{children}</div>
    </section>
  );
}
