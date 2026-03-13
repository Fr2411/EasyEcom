import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function FinancePage() {
  return (
    <PageShell title="Finance" description="Track expenses, receivables, payables, and cash movement with tenant-safe data.">
      <ResetPlaceholder moduleName="Finance" />
    </PageShell>
  );
}
