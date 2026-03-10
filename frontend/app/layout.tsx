import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'EasyEcom Frontend',
  description: 'Next.js SaaS frontend for EasyEcom operations.'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
