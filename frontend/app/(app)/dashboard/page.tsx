import { DashboardAnalyticsWorkspace } from '@/components/dashboard/analytics-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function DashboardPage() {
  return (
    <PageShell
      title="Dashboard"
      description="Track month-to-date business performance, stock health, product opportunity signals, and operational movement from tenant-safe transactional truth."
      hideHeader
    >
      <DashboardAnalyticsWorkspace />
    </PageShell>
  );
}
