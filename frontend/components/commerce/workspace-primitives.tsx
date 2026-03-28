'use client';

import { HoverHint } from '@/components/ui/hover-hint';

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
  hint,
  hintLabel,
  actions,
  children,
}: {
  title: React.ReactNode;
  description?: string;
  hint?: string;
  hintLabel?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
}) {
  const helpText = [description, hint].filter(Boolean).join(' ');

  return (
    <section className="workspace-panel">
      <header className="workspace-panel-header">
        <div>
          <h3>
            {typeof title === 'string' ? (
              <span className="workspace-heading">
                {title}
                {helpText ? <HoverHint text={helpText} label={hintLabel ?? `${title} help`} /> : null}
              </span>
            ) : (
              title
            )}
          </h3>
        </div>
        {actions ? <div className="workspace-panel-actions">{actions}</div> : null}
      </header>
      <div className="workspace-panel-body">{children}</div>
    </section>
  );
}

export const WorkspaceHint = HoverHint;


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
