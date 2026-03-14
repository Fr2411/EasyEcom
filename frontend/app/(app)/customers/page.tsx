import { PageShell } from '@/components/ui/page-shell';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Customer data stays embedded inside Sales and Returns instead of living as a browsable tenant directory.">
      <WorkspacePanel
        title="Embedded customer records"
        description="UI users find customers by phone or email during a transaction. There is no standalone customer list for tenant teams."
      >
        <WorkspaceNotice>
          Customer data is still stored for orders, returns, aggregate reporting, and future AI workflows, but day-to-day access stays inside transaction flows.
        </WorkspaceNotice>
      </WorkspacePanel>
    </PageShell>
  );
}
