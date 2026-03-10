import { PageShell } from '@/components/ui/page-shell';
import { DashboardOverviewPanel } from '@/components/dashboard/dashboard-overview';

export default function DashboardPage() {
  return (
    <PageShell
      title="Dashboard"
      description="Operational snapshot of catalog and inventory performance for your workspace."
    >
      <DashboardOverviewPanel />
    </PageShell>
  );
}
