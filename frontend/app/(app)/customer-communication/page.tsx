import { CustomerCommunicationWorkspace } from '@/components/customer-communication/customer-communication-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function CustomerCommunicationPage() {
  return (
    <PageShell
      title="Customer Communication"
      description="Manage assistant playbooks, channels, conversations, grounded tool calls, and escalations."
      hideHeader
    >
      <CustomerCommunicationWorkspace />
    </PageShell>
  );
}
