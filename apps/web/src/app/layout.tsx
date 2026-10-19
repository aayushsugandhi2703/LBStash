import type { Metadata } from 'next';
import { Geist, Geist_Mono } from 'next/font/google';
import './globals.css';

// Self-hosted at build time by next/font: no request to Google from the browser (README 15.6).
const geist = Geist({ subsets: ['latin'], weight: ['300', '400', '500', '600'], variable: '--font-geist', display: 'swap' });
const geistMono = Geist_Mono({ subsets: ['latin'], weight: ['400', '500'], variable: '--font-geist-mono', display: 'swap' });

export const metadata: Metadata = { title: 'Ledger', description: 'A private budget tracker', robots: { index: false, follow: false } };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${geist.variable} ${geistMono.variable}`}>
      <body>{children}</body>
    </html>
  );
}
