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
        <div>
          <h2>
            <span className="workspace-heading">
              {title}
              <HoverHint text={description} label={`${title} page help`} />
            </span>
          </h2>
        </div>
        <span className="page-shell-chip">Pilot Workspace</span>
      </header>
      <div className="page-shell-body">{children}</div>
    </section>
  );
}
