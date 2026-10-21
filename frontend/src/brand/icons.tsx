import type { SVGProps } from 'react';

/** 24-unit line icons: nav links (16px) and the big pale glyph in each aside. One map, used by both. */
const ICONS = {
  now: 'M20 12a8 8 0 1 0-16 0a8 8 0 1 0 16 0Z M11 12a1 1 0 1 0 2 0a1 1 0 1 0-2 0Z',
  money: 'M5 7h14 M5 12h14 M5 17h9',
  budget: 'M4 4h7v7H4Z M13 4h7v7h-7Z M4 13h7v7H4Z M13 13h7v7h-7Z',
  forecast: 'M4 20h16 M5 16l4.5-5 3.5 3L19 7 M15 7h4v4',
  account: 'M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8Z M4 20c0-4 4-6 8-6s8 2 8 6',
  security: 'M12 3l7 3v6c0 4.5-3 7.5-7 9c-4-1.5-7-4.5-7-9V6Z M9 12l2 2l4-4',
  devices: 'M8 3h8a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z M11 18h2',
  look: 'M12 21a9 9 0 1 0 0-18a9 9 0 0 0 0 18Z M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1.9-1.1 1.8 M12 17h.01',
  setup: 'M5 12l4 4l10-10 M4 20h16',
  signin: 'M5 12h14 M13 6l6 6l-6 6',
  create: 'M12 12a4 4 0 1 0 0-8a4 4 0 0 0 0 8Z M4 20c0-4 4-6 8-6 M18 14v6 M15 17h6',
  secure: 'M7 11V8a5 5 0 0 1 10 0v3 M5 11h14v10H5Z',
  reset: 'M5 12a7 7 0 1 1 2.1 5 M5 20v-4h4',
} as const;
export type IconName = keyof typeof ICONS;

export function NavIcon({ name, ...p }: { name: IconName } & SVGProps<SVGSVGElement>) {
  return (
    <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}>
      <path d={ICONS[name]} />
    </svg>
  );
}

/** The big pale mark at the top of each aside: the page's own icon, not a number. */
export function Glyph({ name }: { name: IconName }) {
  return (
    <svg aria-hidden="true" className="glyph" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth=".7" strokeLinecap="round" strokeLinejoin="round">
      <path d={ICONS[name]} />
    </svg>
  );
}
