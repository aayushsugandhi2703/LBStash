'use client';

import { usePathname } from 'next/navigation';
import { useEffect } from 'react';
import { pageIcon } from './brand';

/** Keeps the browser tab icon in step with the page. The server sends the main mark; this swaps in the page's own icon.
 *  Every icon link is swapped, the SVG and the PNGs (Safari uses a PNG). Next can add the links to the head after the page
 *  is up, so a watcher re-applies the icon whenever a link appears. */
export function PageIcon() {
  const path = usePathname();
  useEffect(() => {
    const { svg, png } = pageIcon(path);
    const apply = () => document.querySelectorAll<HTMLLinkElement>('link[rel~="icon"], link[rel="apple-touch-icon"]').forEach((link) => {
      const href = link.type === 'image/svg+xml' ? svg : png;
      if (link.getAttribute('href') !== href) link.setAttribute('href', href);
    });
    apply();
    const watch = new MutationObserver(apply);
    watch.observe(document.head, { childList: true });
    return () => watch.disconnect();
  }, [path]);
  return null;
}
