import { PageShell } from '@/components/ui/page-shell';

export default function DashboardPage() {
  return (
    <PageShell
      title="Dashboard"
      description="Welcome to EasyEcom. Your authenticated workspace is now active."
    >
      <p>Use the navigation to manage stock, sales, customers, and settings.</p>
    </PageShell>
  );
}
