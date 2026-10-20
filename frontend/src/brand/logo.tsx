import type { SVGProps } from 'react';
import { BRAND } from './brand';

/** Square mark in the theme accent. Decorative: give the link or button around it a label. */
export function LogoMark({ size = 24, ...p }: { size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 32 32" {...p}>
      <rect width="32" height="32" fill="var(--accent)" />
      <path d="M10 7v18h13" fill="none" stroke="#fff" strokeWidth="3" strokeLinecap="square" />
      <path d="M15 12h8M15 17h5" fill="none" stroke="#fff" strokeOpacity=".7" strokeWidth="2" strokeLinecap="square" />
    </svg>
  );
}

/** Mark plus wordmark. */
export function Logo({ size = 24 }: { size?: number }) {
  return (
    <span className="logo">
      <LogoMark size={size} />
      <span className="wordmark">{BRAND.wordmark}</span>
    </span>
  );
}
