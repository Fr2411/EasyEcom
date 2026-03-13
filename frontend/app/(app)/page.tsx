import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function HomePage() {
  return (
    <PageShell
      title="Home"
      description="The application shell is preserved while business workflows are rebuilt from a clean foundation."
    >
      <ResetPlaceholder moduleName="Home workspace" />
    </PageShell>
  );
}
