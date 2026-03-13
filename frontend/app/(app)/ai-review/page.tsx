import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function AiReviewPage() {
  return (
    <PageShell title="AI Review Inbox" description="Generate grounded AI response drafts, review edits, and explicitly approve before send.">
      <ResetPlaceholder moduleName="AI review" />
    </PageShell>
  );
}
