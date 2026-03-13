import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function SalesPage() {
  return (
    <PageShell title="Sales" description="Create and track tenant-scoped sales transactions with live stock impact.">
      <ResetPlaceholder moduleName="Sales" />
    </PageShell>
  );
}
