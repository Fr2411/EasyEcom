import Link from 'next/link';
import { PageShell } from '@/components/ui/page-shell';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Customer data stays embedded inside Sales and Returns instead of living as a browsable tenant directory."
      hideHeader
    >
      <WorkspacePanel
        title="Embedded customer records"
        description="UI users find customers by phone or email during a transaction. There is no standalone customer list for tenant teams."
      >
        <WorkspaceNotice>
          Customer data is still stored for orders, returns, aggregate reporting, and future AI workflows, but day-to-day access stays inside transaction flows.
        </WorkspaceNotice>
        <WorkspaceNotice>
          Start from the Sales workspace to create or reuse customers during checkout.
          <div className="workspace-actions">
            <Link href="/sales" className="btn-primary">Go to Sales workspace</Link>
          </div>
        </WorkspaceNotice>
      </WorkspacePanel>
    </PageShell>
  );
}
