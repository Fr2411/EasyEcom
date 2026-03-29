import { PageShell } from '@/components/ui/page-shell';
import { BillingStatusPage } from '@/components/billing/billing-status-page';

export default function BillingCancelPage() {
  return (
    <PageShell
      title="Billing cancelled"
      description="Checkout can exit without changing the backend subscription state, so the workspace always reads the live account status."
    >
      <BillingStatusPage mode="cancel" />
    </PageShell>
  );
}
