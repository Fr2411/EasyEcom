import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function CustomersPage() {
  return (
    <PageShell title="Customers" description="Customer workflows are temporarily blank while the app foundation is rebuilt.">
      <ResetPlaceholder moduleName="Customers" />
    </PageShell>
  );
}
