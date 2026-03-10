import { PageShell } from '@/components/ui/page-shell';
import { FinanceWorkspace } from '@/components/finance/finance-workspace';

export default function FinancePage() {
  return (
    <PageShell title="Finance" description="Track expenses, receivables, payables, and cash movement with tenant-safe data.">
      <FinanceWorkspace />
    </PageShell>
  );
}
