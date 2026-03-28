import { PageShell } from '@/components/ui/page-shell';
import { ReportsWorkspace } from '@/components/reports/reports-workspace';

export default function ReportsPage() {
  return (
    <PageShell title="Reporting & Analytics" description="Track sales, inventory, finance, returns, and purchases with truthful tenant-scoped metrics.">
      <ReportsWorkspace />
    </PageShell>
  );
}
