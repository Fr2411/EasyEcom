import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function ReportsPage() {
  return (
    <PageShell title="Reporting & Analytics" description="Track sales, inventory, finance, returns, and purchases with truthful tenant-scoped metrics.">
      <ResetPlaceholder moduleName="Reports" />
    </PageShell>
  );
}
