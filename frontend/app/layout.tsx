import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/components/auth/auth-provider';

export const metadata: Metadata = {
  title: 'EasyEcom Frontend',
  description: 'Next.js SaaS frontend for EasyEcom operations.',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
