import { FoundationLaunchpad } from '@/components/dashboard/foundation-launchpad';
import { PageShell } from '@/components/ui/page-shell';

export default function DashboardPage() {
  return (
    <PageShell
      title="Dashboard"
      description="You are signed in to the pilot-ready operations foundation while the detailed workflows are rebuilt module by module."
    >
      <FoundationLaunchpad
        title="Pilot rebuild command center"
        subtitle="The dashboard is now focused on the first product-ready release: catalog, inventory, sales, returns, finance, reports, admin, and settings."
      />
    </PageShell>
  );
}
