import { AIAssistantWorkspace } from '@/components/ai/ai-assistant-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function AIAssistantPage() {
  return (
    <PageShell
      title="AI Assistant"
      description="Review website chatbot conversations and copy the tenant website chat snippet."
      hideHeader
    >
      <AIAssistantWorkspace />
    </PageShell>
  );
}
