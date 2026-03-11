'use client';

import { useEffect, useMemo, useState } from 'react';
import { useAuth } from '@/components/auth/auth-provider';
import { disableAutomation, enableAutomation, getAutomationHistory, getAutomationPolicy, getAutomationQueue, patchAutomationPolicy } from '@/lib/api/automation';
import type { AutomationDecision, AutomationPolicy } from '@/types/automation';

const ADMIN_ROLES = new Set(['SUPER_ADMIN', 'CLIENT_OWNER', 'CLIENT_MANAGER']);
const CATEGORY_LABELS: Record<string, string> = {
  product_availability: 'Product availability check',
  stock_availability: 'Stock availability check',
  simple_price_inquiry: 'Simple price inquiry',
  business_hours_basic_info: 'Business hours / basic info',
};

export function AutomationWorkspace() {
  const { user } = useAuth();
  const canAccess = useMemo(() => Boolean(user?.roles?.some((role) => ADMIN_ROLES.has(role))), [user?.roles]);
  const [policy, setPolicy] = useState<AutomationPolicy | null>(null);
  const [history, setHistory] = useState<AutomationDecision[]>([]);
  const [queue, setQueue] = useState<AutomationDecision[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function loadAll() {
    setLoading(true);
    setError('');
    try {
      const [policyResp, historyResp, queueResp] = await Promise.all([getAutomationPolicy(), getAutomationHistory(), getAutomationQueue()]);
      setPolicy(policyResp);
      setHistory(historyResp.items);
      setQueue(queueResp.items);
    } catch {
      setError('Unable to load automation configuration.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!canAccess) {
      setLoading(false);
      return;
    }
    void loadAll();
  }, [canAccess]);

  async function onToggleCategory(category: string, enabled: boolean) {
    if (!policy) return;
    setBusy(true);
    try {
      const next = await patchAutomationPolicy({ categories: { [category]: enabled } });
      setPolicy(next);
    } finally {
      setBusy(false);
    }
  }

  if (!canAccess) return <div className="admin-card" data-testid="automation-access-denied"><h3>Automation access denied</h3><p>Only tenant owner/manager roles can govern automation policy.</p></div>;
  if (loading) return <div className="admin-card" data-testid="automation-loading"><h3>Loading automation controls…</h3></div>;
  if (!policy) return <div className="admin-card" data-testid="automation-empty-state"><h3>No automation policy yet</h3><p>Policy will be created automatically when automation is configured.</p></div>;

  return <div className="ai-review-layout">
    <section className="admin-card">
      <h3>Automation governance</h3>
      <p><strong>Status:</strong> {policy.automation_enabled ? 'Enabled' : 'Disabled'} · <strong>Auto-send:</strong> {policy.auto_send_enabled ? 'Enabled' : 'Review-first'} · <strong>Emergency stop:</strong> {policy.emergency_disabled ? 'Active' : 'Inactive'}</p>
      <div className="ai-review-actions">
        <button disabled={busy || policy.automation_enabled} onClick={async () => { setBusy(true); await enableAutomation(); await loadAll(); setBusy(false); }}>Enable</button>
        <button disabled={busy || !policy.automation_enabled} onClick={async () => { setBusy(true); await disableAutomation(false); await loadAll(); setBusy(false); }}>Disable</button>
        <button disabled={busy} onClick={async () => { setBusy(true); await disableAutomation(true); await loadAll(); setBusy(false); }}>Emergency disable</button>
      </div>
      <label><input type="checkbox" checked={policy.auto_send_enabled} onChange={async (e) => { setBusy(true); const next = await patchAutomationPolicy({ auto_send_enabled: e.target.checked }); setPolicy(next); setBusy(false); }} /> Allow auto-send for grounded low-risk replies</label>
    </section>

    <section className="admin-card">
      <h3>Low-risk categories</h3>
      <ul className="ai-review-queue">
        {Object.entries(policy.categories).map(([key, enabled]) => <li key={key}><label><input type="checkbox" checked={enabled} disabled={busy} onChange={(e) => void onToggleCategory(key, e.target.checked)} /> {CATEGORY_LABELS[key] || key}</label></li>)}
      </ul>
      {error ? <p className="admin-error">{error}</p> : null}
    </section>

    <section className="admin-card">
      <h3>Escalation queue</h3>
      {queue.length === 0 ? <p data-testid="automation-queue-empty">No escalations pending.</p> : <ul className="integrations-events">{queue.map((row) => <li key={row.decision_id}><strong>{row.outcome}</strong> · {row.category}<br /><small>{row.reason}</small></li>)}</ul>}
      <h3>Decision history</h3>
      {history.length === 0 ? <p data-testid="automation-history-empty">No automation decisions recorded yet.</p> : <ul className="integrations-events">{history.map((row) => <li key={row.decision_id}><strong>{row.outcome}</strong> · {row.recommended_action} · {row.category}<br /><small>{row.reason}</small></li>)}</ul>}
    </section>
  </div>;
}
