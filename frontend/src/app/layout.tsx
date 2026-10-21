import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { BRAND, PageIcon } from '@/brand';
import { ScrollReveal } from '@/components/scroll-reveal';
import { ThemeSync } from '@/components/theme-sync';
import { MODE_SCRIPT } from '@/lib/mode';

// Self-hosted at build time by next/font: no request to Google from the browser (README 15.6).
const geist = Geist({ subsets: ['latin'], weight: ['300', '400', '500', '600'], variable: '--font-geist', display: 'swap' });
const geistMono = Geist_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-geist-mono', display: 'swap' });

export const metadata: Metadata = { title: BRAND.name, description: BRAND.tagline, icons: { icon: [{ url: BRAND.mark, type: 'image/svg+xml', sizes: 'any' }, { url: BRAND.appleIcon, type: 'image/png', sizes: '180x180' }], apple: BRAND.appleIcon }, robots: { index: false, follow: false } };

// viewport-fit=cover uses the whole iPhone screen; CSS keeps content clear of the notch and home bar (env(safe-area-inset-*)).
export const viewport: Viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover', themeColor: [{ media: '(prefers-color-scheme: light)', color: '#FFFFFF' }, { media: '(prefers-color-scheme: dark)', color: '#0E0E10' }] };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // suppressHydrationWarning: the script in <head> sets data-mode before React hydrates. data-scroll-behavior: with smooth scrolling on, Next
    // jumps (not glides) to the top on a route change (Next 16 no longer does this by itself).
    <html lang="en" className={`${geist.variable} ${geistMono.variable}`} data-scroll-behavior="smooth" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: MODE_SCRIPT }} /></head>
      <body>{children}<ScrollReveal /><PageIcon /><ThemeSync /></body>
    </html>
  );
}
