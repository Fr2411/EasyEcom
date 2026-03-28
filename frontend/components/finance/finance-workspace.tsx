'use client';

import { useEffect, useState } from 'react';
import { WorkspaceEmpty, WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';
import { getFinanceOverview } from '@/lib/api/finance';
import { formatMoney } from '@/lib/commerce-format';

type FinanceCardKey = keyof Awaited<ReturnType<typeof getFinanceOverview>>;

const CARDS: Array<{ key: FinanceCardKey; label: string }> = [
  { key: 'sales_revenue', label: 'Sales revenue' },
  { key: 'expense_total', label: 'Expenses' },
  { key: 'receivables', label: 'Receivables' },
  { key: 'payables', label: 'Payables' },
  { key: 'cash_in', label: 'Cash in' },
  { key: 'cash_out', label: 'Cash out' },
  { key: 'net_operating', label: 'Net operating' },
];

export function FinanceWorkspace() {
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof getFinanceOverview>> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    void getFinanceOverview()
      .then((payload) => {
        if (!active) return;
        setOverview(payload);
        setError('');
      })
      .catch((loadError) => {
        if (!active) return;
        setError(loadError instanceof Error ? loadError.message : 'Unable to load finance overview.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  if (loading) {
    return <div className="reports-loading">Loading finance overview…</div>;
  }

  if (error) {
    return <div className="reports-error">{error}</div>;
  }

  if (!overview) {
    return <WorkspaceEmpty title="Finance overview unavailable" message="No finance data was returned for this tenant." />;
  }

  return (
    <div className="finance-module">
      <WorkspaceNotice tone="info">
        Finance detail endpoints stay frozen until canonical ledger-backed subledgers are rebuilt. The overview below is live and tenant-scoped.
      </WorkspaceNotice>
      <div className="finance-cards">
        {CARDS.map((card) => (
          <article key={card.key} className="ps-card">
            <p>{card.label}</p>
            <strong>{formatMoney(overview[card.key])}</strong>
          </article>
        ))}
      </div>
      <WorkspacePanel
        title="Operating posture"
        description="Use this view for cash visibility while deeper accounting helpers remain intentionally disabled."
      >
        <div className="settings-context">
          <div>
            <dt>Collections pressure</dt>
            <dd>{formatMoney(overview.receivables)} still outstanding from confirmed sales.</dd>
          </div>
          <div>
            <dt>Expense load</dt>
            <dd>{formatMoney(overview.expense_total)} recorded against this tenant so far.</dd>
          </div>
          <div>
            <dt>Cash movement</dt>
            <dd>
              In {formatMoney(overview.cash_in)} / out {formatMoney(overview.cash_out)}.
            </dd>
          </div>
        </div>
      </WorkspacePanel>
    </div>
  );
}
