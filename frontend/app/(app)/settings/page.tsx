import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function SettingsPage() {
  return (
    <PageShell
      title="Settings"
      description="Business profile, operational preferences, and tenant configuration controls."
    >
      <ResetPlaceholder moduleName="Settings" />
    </PageShell>
  );
}
