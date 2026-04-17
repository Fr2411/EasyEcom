import { PageShell } from '@/components/ui/page-shell';
import { BillingWorkspace } from '@/components/billing/billing-workspace';

export default function BillingPage() {
  return (
    <PageShell
      title="Billing"
      description="Owner-only billing workspace that trusts backend subscription state, separates plan changes from hosted billing actions, and keeps redirects explicit."
      hideHeader
    >
      <BillingWorkspace />
    </PageShell>
  );
}
