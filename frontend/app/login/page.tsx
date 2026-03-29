import type { Metadata } from 'next';
import { AuthPageView } from '@/components/auth/auth-page-view';

export const metadata: Metadata = {
  title: 'Login | EasyEcom',
  description: 'Sign in to your EasyEcom workspace and manage sales, inventory, and operations in one place.',
  openGraph: {
    title: 'Login | EasyEcom',
    description: 'Sign in to your EasyEcom workspace and manage sales, inventory, and operations in one place.',
  },
};

export default function LoginPage() {
  return <AuthPageView mode="login" />;
}
