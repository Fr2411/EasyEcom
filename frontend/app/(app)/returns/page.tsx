import { PageShell } from '@/components/ui/page-shell';
import { ReturnsWorkspace } from '@/components/returns/returns-workspace';

export default function ReturnsPage() {
  return (
    <PageShell title="Returns" description="Record tenant-scoped sales returns with stock restoration and truthful finance impact.">
      <ReturnsWorkspace />
    </PageShell>
  );
}
