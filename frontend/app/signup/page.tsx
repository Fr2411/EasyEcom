import type { Metadata } from 'next';
import { AuthPageView } from '@/components/auth/auth-page-view';

export const metadata: Metadata = {
  title: 'Sign Up | EasyEcom',
  description: 'Create your EasyEcom account and start free in minutes.',
  openGraph: {
    title: 'Sign Up | EasyEcom',
    description: 'Create your EasyEcom account and start free in minutes.',
  },
};

export default function SignupPage() {
  return <AuthPageView mode="signup" />;
}
