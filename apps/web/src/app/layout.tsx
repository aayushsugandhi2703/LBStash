import type { Metadata, Viewport } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';
import { BRAND } from '@/brand';
import { ScrollReveal } from '@/components/scroll-reveal';

// Self-hosted at build time by next/font: no request to Google from the browser (README 15.6).
const geist = Geist({ subsets: ['latin'], weight: ['300', '400', '500', '600'], variable: '--font-geist', display: 'swap' });
const geistMono = Geist_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-geist-mono', display: 'swap' });

export const metadata: Metadata = { title: BRAND.name, description: BRAND.tagline, icons: { icon: BRAND.mark }, robots: { index: false, follow: false } };

// viewport-fit=cover uses the whole iPhone screen; CSS keeps content clear of the notch and home bar (env(safe-area-inset-*)).
export const viewport: Viewport = { width: 'device-width', initialScale: 1, viewportFit: 'cover', themeColor: '#FFFFFF' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable}`}>
      <body>{children}<ScrollReveal /></body>
    </html>
  );
}
