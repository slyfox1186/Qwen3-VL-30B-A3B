import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { ThemeProvider } from "@/components/theme";
import { ObservabilityProvider } from "@/components/observability";
import "@/styles/index.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Qwen3-VL Chat",
  description: "Multimodal vision chat with Qwen3-VL-30B-A3B",
};

// Inline script to prevent flash of wrong theme (runs before React hydrates)
const themeInitScript = `
(function() {
  try {
    const stored = localStorage.getItem('theme-storage');
    let theme = 'system';
    if (stored) {
      const parsed = JSON.parse(stored);
      theme = parsed.state?.theme || 'system';
    }
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    const isDark = theme === 'dark' || (theme === 'system' && prefersDark);
    if (isDark) {
      document.documentElement.classList.add('dark');
    }
  } catch (e) {
    document.documentElement.classList.add('dark');
  }
})();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <ObservabilityProvider sentryDsn={process.env.NEXT_PUBLIC_SENTRY_DSN}>
          <ThemeProvider>
            {children}
          </ThemeProvider>
        </ObservabilityProvider>
      </body>
    </html>
  );
}
