import { PageShell } from '@/components/ui/page-shell';
import { CustomersWorkspace } from '@/components/customers/customers-workspace';

export default function CustomersPage() {
  return (
    <PageShell
      title="Customers"
      description="Search customer records, review recent activity, and jump into the right transaction workflow."
      hideHeader
    >
      <CustomersWorkspace />
    </PageShell>
  );
}
