import { AiReviewWorkspace } from '@/components/ai-review/ai-review-workspace';
import { PageShell } from '@/components/ui/page-shell';

export default function AiReviewPage() {
  return <PageShell title="AI Review Inbox" description="Generate grounded AI response drafts, review edits, and explicitly approve before send."><AiReviewWorkspace /></PageShell>;
}
