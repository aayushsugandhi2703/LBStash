/** Name, tagline and asset paths in one place; the files live in `public/brand`. */
export const BRAND = {
  name: 'LBStash',
  wordmark: 'LBStash',
  tagline: 'A private budget tracker',
  color: '#00875A',
  // Browsers keep tab icons for days, keyed by URL: change `v` whenever mark.svg or favicon.ico changes.
  mark: '/brand/mark.svg?v=2',
  appleIcon: '/brand/apple-touch-icon.png?v=2',
  logo: '/brand/logo.svg',
} as const;

/** Tab icon per page: first matching path prefix wins, so list the longer paths first. Files are `public/brand/pages/<name>.favicon.svg` and `.favicon.png`. */
const PAGE_ICONS: readonly (readonly [prefix: string, name: string])[] = [
  ['/account/security', 'security'],
  ['/account/devices', 'devices'],
  ['/account', 'account'],
  ['/money', 'money'],
  ['/budget', 'budget'],
  ['/forecast', 'forecast'],
  ['/setup', 'setup'],
  ['/sign-in', 'sign-in'],
  ['/create-account', 'create-account'],
  ['/reset', 'reset'],
  ['/secure', 'secure'],
];

/** The tab icon for a path, as an SVG and as a PNG: the page's own icon, or the main mark for the home page and anything unlisted.
 *  Safari does not show SVG tab icons and prefers the PNG, so both are always given. */
export function pageIcon(path: string): { svg: string; png: string } {
  const hit = PAGE_ICONS.find(([prefix]) => path === prefix || path.startsWith(`${prefix}/`));
  return hit
    ? { svg: `/brand/pages/${hit[1]}.favicon.svg`, png: `/brand/pages/${hit[1]}.favicon.png` }
    : { svg: BRAND.mark, png: BRAND.appleIcon };
}
