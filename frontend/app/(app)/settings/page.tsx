import { PageShell } from '@/components/ui/page-shell';
import { SettingsWorkspace } from '@/components/settings/settings-workspace';

export default function SettingsPage() {
  return (
    <PageShell
      title="Settings"
      description="Business profile, operational preferences, and tenant configuration controls."
      hideHeader
    >
      <SettingsWorkspace />
    </PageShell>
  );
}
