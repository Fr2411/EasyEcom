import { PageShell } from '@/components/ui/page-shell';
import { AutomationWorkspace } from '@/components/automation/automation-workspace';

export default function AutomationPage() {
  return (
    <PageShell
      title="Automation"
      description="Review tenant-safe automation readiness, configured rules, and recent run history while write paths remain intentionally locked down."
    >
      <AutomationWorkspace />
    </PageShell>
  );
}
