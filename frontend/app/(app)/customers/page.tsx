import Link from 'next/link';
import { PageShell } from '@/components/ui/page-shell';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Use this page to jump into the right customer workflow quickly."
      hideHeader
    >
      <WorkspacePanel
        title="Customer work starts from Sales or Returns"
        description="Pick the transaction workspace first. Customer records are created and maintained there."
      >
        <WorkspaceNotice>
          Finish customer tasks fastest by opening the right transaction flow first.
        </WorkspaceNotice>
        <div className="workspace-actions customers-action-strip">
          <Link href="/sales" className="btn-primary customers-action-btn">Open Sales</Link>
          <Link href="/returns" className="btn-primary customers-action-btn">Open Returns</Link>
        </div>
        <div className="customers-purpose-card" aria-label="Sales versus returns guidance">
          <p className="customers-purpose-summary">
            Choose the action by intent:
          </p>
          <ul className="customers-purpose-guidance">
            <li><strong>Sales:</strong> New or repeat order, checkout updates, and order confirmation.</li>
            <li><strong>Returns:</strong> Exchange, refund, or post-sale follow-up and history checks.</li>
          </ul>
        </div>
        <WorkspaceNotice>
          Customer data remains available for orders, returns, reporting, and AI workflows.
        </WorkspaceNotice>
        <WorkspaceNotice>
          Keep updates in transaction workspaces so audit trails stay complete.
        </WorkspaceNotice>
      </WorkspacePanel>

      <WorkspacePanel
        title="Supporting context"
        description="Reference details that are useful but not required before taking action."
        className="customers-utility-panel"
      >
        <WorkspaceNotice>
          There is no standalone customer directory in daily operations.
        </WorkspaceNotice>
        <WorkspaceNotice>
          Sales and returns write customer records in the same tenant-safe operational flow.
        </WorkspaceNotice>
        <div className="workspace-actions customers-action-strip customers-action-strip-secondary">
          <Link href="/sales" className="btn-primary customers-action-btn">Start in Sales</Link>
          <Link href="/returns" className="btn-primary customers-action-btn">Start in Returns</Link>
        </div>
      </WorkspacePanel>
    </PageShell>
  );
}
