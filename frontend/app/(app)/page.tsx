import { FoundationLaunchpad } from '@/components/dashboard/foundation-launchpad';
import { PageShell } from '@/components/ui/page-shell';

export default function HomePage() {
  return (
    <PageShell
      title="Home"
      description="The application shell is preserved while business workflows are rebuilt from a clean, tenant-safe foundation."
    >
      <FoundationLaunchpad
        title="The product foundation is live again."
        subtitle="This workspace now reflects the canonical module structure for the pilot release. Each module can be rebuilt intentionally without reviving the old calculation bugs."
      />
    </PageShell>
  );
}
