import { AppShell } from '@/components/layout/app-shell';
import { AuthRouteGuard } from '@/components/auth/auth-route-guard';

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthRouteGuard mode="protected">
      <AppShell>{children}</AppShell>
    </AuthRouteGuard>
  );
}
