'use client';

export function WorkspaceTabs<T extends string>({
  tabs,
  activeTab,
  onTabChange,
}: {
  tabs: Array<{ id: T; label: string }>;
  activeTab: T;
  onTabChange: (tab: T) => void;
}) {
  return (
    <div className="workspace-tabs" role="tablist" aria-label="Workspace tabs">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          role="tab"
          aria-selected={activeTab === tab.id}
          className={activeTab === tab.id ? 'workspace-tab active' : 'workspace-tab'}
          onClick={() => onTabChange(tab.id)}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}


export function WorkspacePanel({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="workspace-panel">
      <header className="workspace-panel-header">
        <div>
          <h3>{title}</h3>
          {description ? <p>{description}</p> : null}
        </div>
        {actions ? <div className="workspace-panel-actions">{actions}</div> : null}
      </header>
      <div className="workspace-panel-body">{children}</div>
    </section>
  );
}


export function WorkspaceNotice({
  tone = 'info',
  children,
}: {
  tone?: 'info' | 'success' | 'error';
  children: React.ReactNode;
}) {
  return <div className={`workspace-notice ${tone}`}>{children}</div>;
}


export function WorkspaceToast({
  tone = 'success',
  message,
  onClose,
}: {
  tone?: 'success' | 'error';
  message: string;
  onClose: () => void;
}) {
  return (
    <div className={`workspace-toast ${tone}`} role="status" aria-live="polite">
      <span>{message}</span>
      <button type="button" onClick={onClose} aria-label="Close message">Close</button>
    </div>
  );
}


export function WorkspaceEmpty({
  title,
  message,
}: {
  title: string;
  message: string;
}) {
  return (
    <div className="workspace-empty">
      <h4>{title}</h4>
      <p>{message}</p>
    </div>
  );
}
