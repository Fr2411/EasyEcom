'use client';

import { HoverHint } from '@/components/ui/hover-hint';
import type { SuggestedAction } from '@/types/guided-workflow';

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

export function IntentInput({
  label,
  hint,
  value,
  placeholder,
  pending = false,
  submitLabel = 'Continue',
  onChange,
  onSubmit,
  children,
}: {
  label: string;
  hint?: string;
  value: string;
  placeholder: string;
  pending?: boolean;
  submitLabel?: string;
  onChange: (value: string) => void;
  onSubmit: () => void | Promise<void>;
  children?: React.ReactNode;
}) {
  return (
    <section className="guided-intent">
      <div className="guided-intent-copy">
        <p className="eyebrow">Intent-first workflow</p>
        <h4>{label}</h4>
        {hint ? <p>{hint}</p> : null}
      </div>
      <form
        className="guided-intent-form"
        onSubmit={(event) => {
          event.preventDefault();
          void onSubmit();
        }}
      >
        <input
          type="search"
          value={value}
          placeholder={placeholder}
          onChange={(event) => onChange(event.target.value)}
        />
        <button type="submit" className="btn-primary" disabled={pending}>
          {pending ? 'Looking up…' : submitLabel}
        </button>
      </form>
      {children ? <div className="guided-intent-support">{children}</div> : null}
    </section>
  );
}

export function SuggestedNextStep({
  suggestion,
  onPrimary,
  onSecondary,
}: {
  suggestion: SuggestedAction;
  onPrimary?: () => void;
  onSecondary?: () => void;
}) {
  return (
    <div className={`guided-next-step ${suggestion.tone ?? 'info'}`}>
      <div>
        <p className="eyebrow">Recommended next step</p>
        <strong>{suggestion.title}</strong>
        <p>{suggestion.detail}</p>
      </div>
      {suggestion.actionLabel || suggestion.secondaryLabel ? (
        <div className="guided-next-step-actions">
          {suggestion.secondaryLabel ? (
            <button type="button" className="secondary" onClick={onSecondary}>
              {suggestion.secondaryLabel}
            </button>
          ) : null}
          {suggestion.actionLabel ? (
            <button type="button" className="btn-primary" onClick={onPrimary}>
              {suggestion.actionLabel}
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function MatchGroupList<T>({
  title,
  description,
  items,
  emptyMessage,
  renderItem,
}: {
  title: string;
  description?: string;
  items: T[];
  emptyMessage?: string;
  renderItem: (item: T, index: number) => React.ReactNode;
}) {
  if (!items.length) {
    return emptyMessage ? (
      <div className="guided-match-group">
        <div className="guided-match-group-header">
          <h4>{title}</h4>
          {description ? <p>{description}</p> : null}
        </div>
        <div className="workspace-empty compact">
          <p>{emptyMessage}</p>
        </div>
      </div>
    ) : null;
  }

  return (
    <section className="guided-match-group">
      <div className="guided-match-group-header">
        <h4>{title}</h4>
        {description ? <p>{description}</p> : null}
      </div>
      <div className="guided-match-list">{items.map(renderItem)}</div>
    </section>
  );
}

export function DraftRecommendationCard({
  title,
  summary,
  actions,
  children,
}: {
  title: string;
  summary: string;
  actions?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <section className="guided-draft-card">
      <div className="guided-draft-card-header">
        <div>
          <p className="eyebrow">Staged draft</p>
          <h4>{title}</h4>
          <p>{summary}</p>
        </div>
        {actions ? <div className="guided-draft-card-actions">{actions}</div> : null}
      </div>
      {children ? <div className="guided-draft-card-body">{children}</div> : null}
    </section>
  );
}

export function StagedActionFooter({
  summary,
  children,
}: {
  summary: string;
  children: React.ReactNode;
}) {
  return (
    <footer className="guided-action-footer">
      <p>{summary}</p>
      <div className="guided-action-footer-actions">{children}</div>
    </footer>
  );
}
