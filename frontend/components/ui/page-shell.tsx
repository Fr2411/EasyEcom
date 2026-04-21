import { HoverHint } from '@/components/ui/hover-hint';

export function PageShell({
  title,
  description,
  children,
  hideHeader = false,
}: {
  title: string;
  description: string;
  children?: React.ReactNode;
  hideHeader?: boolean;
}) {
  return (
    <section className="page-shell">
      {!hideHeader ? (
        <header className="page-shell-header">
          <div className="page-shell-copy">
            <h2>
              <span className="workspace-heading">
                {title}
                <HoverHint text={description} label={`${title} page help`} />
              </span>
            </h2>
          </div>
        </header>
      ) : null}
      <div className="page-shell-body">{children}</div>
    </section>
  );
}
