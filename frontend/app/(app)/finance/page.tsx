import { PageShell } from '@/components/ui/page-shell';
import { FinanceWorkspace } from '@/components/finance/finance-workspace';

export default function FinancePage() {
  return (
    <PageShell title="Finance" description="Track commerce-origin sales and refund events, manual operating cash, receivables, and refund history."
      hideHeader
    >
      <FinanceWorkspace />
    </PageShell>
  );
}
