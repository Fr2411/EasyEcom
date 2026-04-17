import { PageShell } from '@/components/ui/page-shell';
import { CatalogWorkspace } from '@/components/commerce/catalog-workspace';

export default function CatalogPage() {
  return (
    <PageShell
      title="Catalog"
      description="Advanced maintenance for parent products and saleable variants. Daily intake now starts in Receive Stock."
      hideHeader
    >
      <CatalogWorkspace />
    </PageShell>
  );
}
