'use client';
import { useEffect } from 'react';

/** Blocks that fade in on scroll: page columns, their direct blocks and every row. Anything on screen at first paint is left alone. */
const SELECTOR = '.main > *, .aside > *, .signin-main > *, .signin-aside > *, .row, .settings-row, .idx, .well, h2.h2';
/** Scrolling faster than this (px per ms) shows blocks at once: an animation would only lag behind the finger. */
const FAST = 0.8;

/** Lazy reveal on scroll for the whole app: marks off-screen blocks `data-reveal`, starts them early and adds `data-in`. */
export function ScrollReveal() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches || !('IntersectionObserver' in window)) return;
    const seen = new WeakSet<Element>();
    let fast = false;
    const last = new WeakMap<EventTarget, { y: number; t: number }>();
    let calm = 0;
    const mounted = performance.now();
    const onScroll = (e: Event) => {
      const t = e.target === document ? window : (e.target as HTMLElement);
      const y = t instanceof Window ? window.scrollY : t.scrollTop;
      const now = performance.now();
      const prev = last.get(e.target as EventTarget) ?? { y: 0, t: mounted }; // the very first jump counts too
      last.set(e.target as EventTarget, { y, t: now });
      if (now > prev.t && Math.abs(y - prev.y) / (now - prev.t) > FAST) fast = true;
      window.clearTimeout(calm);
      calm = window.setTimeout(() => { fast = false; }, 120);
    };
    window.addEventListener('scroll', onScroll, { passive: true, capture: true });

    const io = new IntersectionObserver(
      (entries) => {
        let i = 0;
        for (const e of entries) {
          if (!e.isIntersecting) continue;
          const el = e.target as HTMLElement;
          if (fast) el.setAttribute('data-instant', '');
          else el.style.setProperty('--reveal-delay', `${Math.min(i++, 4) * 40}ms`);
          el.setAttribute('data-in', '');
          io.unobserve(el);
        }
      },
      { rootMargin: '0px 0px 30% 0px', threshold: 0 }, // start early (a third of a screen ahead), so it is already there when it arrives
    );
    const scan = (root: ParentNode) => {
      root.querySelectorAll(SELECTOR).forEach((el) => {
        if (seen.has(el) || el.classList.contains('rise')) return;
        seen.add(el);
        const r = el.getBoundingClientRect();
        if (r.top < window.innerHeight * 1.3 && r.bottom > 0) return; // on screen or about to be: no flash
        el.setAttribute('data-reveal', '');
        io.observe(el);
      });
    };
    scan(document);
    // content arrives later (data loads, route changes): pick it up
    let pending = 0;
    const mo = new MutationObserver(() => {
      window.cancelAnimationFrame(pending);
      pending = window.requestAnimationFrame(() => scan(document));
    });
    mo.observe(document.body, { childList: true, subtree: true });
    return () => {
      window.removeEventListener('scroll', onScroll, { capture: true });
      mo.disconnect(); io.disconnect(); window.cancelAnimationFrame(pending); window.clearTimeout(calm);
    };
  }, []);
  return null;
}
