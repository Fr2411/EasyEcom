'use client';

import { useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getAutomationOverview, getAutomationRules, getAutomationRuns } from '@/lib/api/automation';

type AutomationState = {
  overview: Awaited<ReturnType<typeof getAutomationOverview>>;
  rules: Awaited<ReturnType<typeof getAutomationRules>>;
  runs: Awaited<ReturnType<typeof getAutomationRuns>>;
};

export function AutomationWorkspace() {
  const [state, setState] = useState<AutomationState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void Promise.all([getAutomationOverview(), getAutomationRules(), getAutomationRuns()])
      .then(([overview, rules, runs]) => {
        if (!active) return;
        setState({ overview, rules, runs });
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load automation workspace.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="reports-loading">Loading automation workspace…</div>;
  }

  if (error) {
    return <div className="reports-error">{error}</div>;
  }

  if (!state) {
    return <WorkspaceEmpty title="Automation unavailable" message="No automation data was returned for this tenant." />;
  }

  return (
    <div className="reports-module">
      <WorkspaceNotice tone="info">
        Automation writes remain disabled until rule execution, audit logging, and tenant-safe policy storage are completed. This workspace exposes the live control surface that will own that rollout.
      </WorkspaceNotice>

      <div className="reports-grid">
        {state.overview.metrics.map((metric) => (
          <article key={metric.label} className="ps-card">
            <p>{metric.label}</p>
            <strong>{metric.value}</strong>
            {metric.hint ? <span className="muted">{metric.hint}</span> : null}
          </article>
        ))}
      </div>

      <WorkspacePanel title="Automation readiness" description={state.overview.summary}>
        <div className="settings-context">
          <div>
            <dt>Module status</dt>
            <dd>{state.overview.status}</dd>
          </div>
          <div>
            <dt>Rule catalog</dt>
            <dd>{state.rules.items.length ? `${state.rules.items.length} rules available` : 'No automation rules are configured yet.'}</dd>
          </div>
          <div>
            <dt>Execution history</dt>
            <dd>{state.runs.items.length ? `${state.runs.items.length} recent runs available` : 'No automation runs have been recorded yet.'}</dd>
          </div>
        </div>
      </WorkspacePanel>

      <WorkspacePanel title="Configured rules" description="Rules will appear here once tenant-safe scheduling and action policies are enabled.">
        {state.rules.items.length ? (
          <ul className="admin-match-list">
            {state.rules.items.map((rule) => (
              <li key={rule.automation_rule_id}>
                <strong>{rule.name}</strong>
                <p className="muted">
                  {rule.status} • {rule.trigger_type}
                </p>
              </li>
            ))}
          </ul>
        ) : (
          <WorkspaceEmpty
            title="No automation rules configured"
            message="Start with low-stock alerts, failed-channel follow-up, and SLA reminders once execution safeguards are implemented."
          />
        )}
      </WorkspacePanel>
    </div>
  );
}
