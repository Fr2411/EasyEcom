import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function AutomationPage() {
  return (
    <PageShell title="Automation" description="Automation controls are temporarily blank while the business logic is rebuilt.">
      <ResetPlaceholder moduleName="Automation" />
    </PageShell>
  );
}
