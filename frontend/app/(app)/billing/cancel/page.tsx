import { PageShell } from '@/components/ui/page-shell';
import { BillingStatusPage } from '@/components/billing/billing-status-page';

export default function BillingCancelPage() {
  return (
    <PageShell
      title="Billing cancelled"
      description="Cancellation requests keep benefits live through the end of the billing cycle, so the workspace always reads the live backend account state."
    >
      <BillingStatusPage mode="cancel" />
    </PageShell>
  );
}
