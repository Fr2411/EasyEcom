import { PageShell } from '@/components/ui/page-shell';
import { ResetPlaceholder } from '@/components/ui/reset-placeholder';

export default function ReturnsPage() {
  return (
    <PageShell title="Returns" description="Record tenant-scoped sales returns with stock restoration and truthful finance impact.">
      <ResetPlaceholder moduleName="Returns" />
    </PageShell>
  );
}
