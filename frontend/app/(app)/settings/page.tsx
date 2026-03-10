import { SettingsWorkspace } from '@/components/settings/settings-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function SettingsPage() {
  return (
    <PageShell
      title="Settings"
      description="Business profile, operational preferences, and tenant configuration controls."
    >
      <SettingsWorkspace />
    </PageShell>
  );
}
