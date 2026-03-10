import { PageShell } from '@/components/ui/page-shell';
import { SalesWorkspace } from '@/components/sales/sales-workspace';

export default function SalesPage() {
  return (
    <PageShell title="Sales" description="Create and track tenant-scoped sales transactions with live stock impact.">
      <SalesWorkspace />
    </PageShell>
  );
}
