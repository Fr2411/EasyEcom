import { FoundationLaunchpad } from '@/components/dashboard/foundation-launchpad';
import { PageShell } from '@/components/ui/page-shell';

export default function WorkspaceHomePage() {
  return (
    <PageShell
      title="Home"
      description="Quick access to the core workspaces."
      hideHeader
    >
      <FoundationLaunchpad
        title="Core workspaces"
        subtitle="Quick links to the main operating modules."
      />
    </PageShell>
  );
}
