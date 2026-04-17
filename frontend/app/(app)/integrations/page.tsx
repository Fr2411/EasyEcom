import { PageShell } from '@/components/ui/page-shell';
import { IntegrationsWorkspace } from '@/components/integrations/integrations-workspace';

export default function IntegrationsPage() {
  return (
    <PageShell title="Integrations & Channels" description="Configure tenant communication channels with explicit verification and auditable message intents."
      hideHeader
    >
      <IntegrationsWorkspace />
    </PageShell>
  );
}
