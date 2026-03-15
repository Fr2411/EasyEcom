import { SalesAgentWorkspace } from '@/components/sales-agent/sales-agent-workspace';
import { PageShell } from '@/components/ui/page-shell';


export default function SalesAgentPage() {
  return (
    <PageShell
      title="Sales Agent"
      description="Monitor WhatsApp conversations, review AI drafts, and confirm agent-created draft orders with full tenant-safe context."
    >
      <SalesAgentWorkspace />
    </PageShell>
  );
}
