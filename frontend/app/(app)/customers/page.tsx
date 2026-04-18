import Link from 'next/link';
import { PageShell } from '@/components/ui/page-shell';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Use this page to choose the fastest place to manage customer work during daily operations."
      hideHeader
    >
      <WorkspacePanel
        title="Start customer work from Sales or Returns"
        description="There is no separate customer directory in the day-to-day flow. Teams create and update customer records while completing sales and returns."
      >
        <WorkspaceNotice>
          Use Sales when creating a new order. Use Returns when handling exchanges, refunds, or post-sale customer follow-up.
        </WorkspaceNotice>
        <WorkspaceNotice>
          Customer records are still available for orders, returns, reporting, and AI workflows, but those records are maintained inside transaction workspaces.
        </WorkspaceNotice>
        <div className="workspace-actions">
          <Link href="/sales" className="btn-primary">Go to Sales workspace</Link>
          <Link href="/returns" className="btn-primary">Go to Returns workspace</Link>
        </div>
      </WorkspacePanel>

      <WorkspacePanel
        title="Common customer tasks"
        description="Quick reminders to help first-time users choose the right flow without scanning multiple pages."
      >
        <WorkspaceNotice>
          <strong>When to use Sales:</strong> first purchase, repeat purchase, contact updates at checkout, and order confirmation.
        </WorkspaceNotice>
        <WorkspaceNotice>
          <strong>When to use Returns:</strong> item return, exchange handling, refund completion, and return history checks.
        </WorkspaceNotice>
      </WorkspacePanel>
    </PageShell>
  );
}
