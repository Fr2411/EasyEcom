import type { Metadata } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import Script from 'next/script';
import './globals.css';
import { AuthProvider } from '@/components/auth/auth-provider';
import { ThemeProvider } from '@/components/theme/theme-provider';

const interSans = Inter({
  subsets: ['latin'],
  variable: '--font-sans',
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
});

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
      <body className={`${interSans.variable} ${jetbrainsMono.variable}`}>
        <ThemeProvider>
          <AuthProvider>{children}</AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
