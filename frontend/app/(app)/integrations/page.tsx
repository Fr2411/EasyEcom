import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function IntegrationsPage() {
  return (
    <PageShell title="Integrations & Channels" description="Configure tenant communication channels with explicit verification and auditable message intents.">
      <ResetPlaceholder moduleName="Integrations" />
    </PageShell>
  );
}
