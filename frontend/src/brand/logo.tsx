import type { SVGProps } from 'react';
import { BRAND } from './brand';

/** Square mark in the theme accent: a lowercase b made of a stem and a coin. Decorative: give the link or button around it a label. */
export function LogoMark({ size = 24, ...p }: { size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 32 32" {...p}>
      <rect width="32" height="32" fill="var(--accent)" />
      <rect x="8" y="5" width="5.5" height="22" fill="#fff" />
      <circle cx="20.5" cy="20.5" r="6.5" fill="#fff" />
    </svg>
  );
}

/** Mark plus wordmark. */
export function Logo({ size = 24 }: { size?: number }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="wordmark">{BRAND.wordmark.slice(0, 2)}<span className="stash">{BRAND.wordmark.slice(2)}</span></span>
    </span>
  );
}
