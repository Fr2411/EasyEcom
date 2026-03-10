import { PageShell } from '@/components/ui/page-shell';
import { CustomersWorkspace } from '@/components/customers/customers-workspace';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Manage your customer profiles for faster sales operations.">
      <CustomersWorkspace />
    </PageShell>
  );
}
