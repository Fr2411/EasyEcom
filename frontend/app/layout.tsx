import type { Metadata } from 'next';
import Script from 'next/script';
import './globals.css';
import { AuthProvider } from '@/components/auth/auth-provider';
import { ThemeProvider } from '@/components/theme/theme-provider';

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
    <html lang="en" suppressHydrationWarning>
      <head>
        <Script id="theme-preference-init" strategy="beforeInteractive">
          {`
            (function () {
              try {
                var stored = window.localStorage.getItem('easyecom-theme-preference') || 'system';
                var resolved = stored === 'system'
                  ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
                  : stored;
                document.documentElement.dataset.theme = resolved;
                document.documentElement.dataset.themePreference = stored;
              } catch (error) {
                document.documentElement.dataset.theme = 'light';
                document.documentElement.dataset.themePreference = 'system';
              }
            })();
          `}
        </Script>
        <Script
          src="https://www.googletagmanager.com/gtag/js?id=G-TJ4YFZFF9L"
          strategy="afterInteractive"
        />
        <Script id="google-analytics" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', 'G-TJ4YFZFF9L');
          `}
        </Script>
      </head>
      <body>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
