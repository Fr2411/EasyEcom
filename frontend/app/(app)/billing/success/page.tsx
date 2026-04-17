import { PageShell } from '@/components/ui/page-shell';
import { BillingStatusPage } from '@/components/billing/billing-status-page';

export default function BillingSuccessPage() {
  return (
    <PageShell
      title="Billing success"
      description="Review the live backend subscription state after PayPal returns the browser to the app."
      hideHeader
    >
      <BillingStatusPage mode="success" />
    </PageShell>
  );
}
