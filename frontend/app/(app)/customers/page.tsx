import Link from 'next/link';
import { PageShell } from '@/components/ui/page-shell';
import { WorkspaceNotice, WorkspacePanel } from '@/components/commerce/workspace-primitives';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Use this page to understand where customer records are created and managed in daily operations."
      hideHeader
    >
      <WorkspacePanel
        title="Customer records live inside transactions"
        description="There is no standalone customer directory. Teams create and reuse customer records during checkout, then update them while handling sales and returns."
      >
        <WorkspaceNotice>
          Customer data is stored for orders, returns, reporting, and future AI workflows, but day-to-day customer work stays inside Sales and Returns.
        </WorkspaceNotice>
        <WorkspaceNotice>
          Primary next action: start in Sales to create or reuse a customer while placing an order.
          <div className="workspace-actions">
            <Link href="/sales" className="btn-primary">Go to Sales workspace</Link>
            <Link href="/returns" className="secondary">Go to Returns workspace</Link>
          </div>
        </WorkspaceNotice>
      </WorkspacePanel>
    </PageShell>
  );
}
