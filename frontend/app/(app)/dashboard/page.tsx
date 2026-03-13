import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function DashboardPage() {
  return (
    <PageShell
      title="Dashboard"
      description="You are signed in to a clean foundation workspace while the new application logic is rebuilt."
    >
      <ResetPlaceholder moduleName="Dashboard" />
    </PageShell>
  );
}
