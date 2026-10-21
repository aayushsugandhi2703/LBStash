'use client';
import { useEffect } from 'react';
import { canScroll, clampTarget, stepToward, wheelPixels } from '@/lib/smooth-scroll';

/** Controls where the wheel must stay native: typing, and any inner list or panel that can scroll itself. */
const NATIVE = 'input, textarea, select, [contenteditable=""], [contenteditable="true"], [data-native-scroll]';

interface Run { target: number; raf: number; last: number }

/**
 * Eased wheel scrolling for the page (compact layout) and for `.scroller` (fixed frame). CSS `scroll-behavior: smooth`
 * only glides jumps and anchors; a wheel notch or a trackpad flick still moves in steps, so this adds the easing.
 * Off with reduced motion. Inner scrollers (side columns, tables, menus) keep the native wheel, and so does everything
 * that is not a mouse wheel (touch, keyboard, scrollbar drag).
 */
export function SmoothScroll() {
  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const runs = new Map<Element, Run>();
    const root = () => document.scrollingElement as HTMLElement | null;
    const view = (el: Element) => (el === root() ? window.innerHeight : el.clientHeight);
    const max = (el: Element) => Math.max(0, el.scrollHeight - view(el));
    const top = (el: Element) => el.scrollTop;
    const jump = (el: Element, y: number) => el.scrollTo({ top: y, behavior: 'instant' as ScrollBehavior });

    function scrollerFor(start: EventTarget | null, dy: number): Element | null {
      let el = start instanceof Element ? start : null;
      while (el && el !== document.body && el !== document.documentElement) {
        if (el.matches(NATIVE)) return null;
        const oy = getComputedStyle(el).overflowY;
        if ((oy === 'auto' || oy === 'scroll') && el.scrollHeight > el.clientHeight + 1 && canScroll(el.scrollTop, el.clientHeight, el.scrollHeight, dy)) {
          return el.classList.contains('scroller') ? el : null; // only the page's own scroll area is eased
        }
        el = el.parentElement;
      }
      const r = root();
      return r && max(r) > 0 && canScroll(r.scrollTop, window.innerHeight, r.scrollHeight, dy) ? r : null;
    }

    function tick(el: Element, run: Run) {
      const now = performance.now();
      const dt = Math.min(now - run.last, 50);
      run.last = now;
      const next = stepToward(top(el), run.target, dt);
      jump(el, next);
      run.raf = next === run.target || Math.abs(top(el) - run.target) < 0.5 ? 0 : requestAnimationFrame(() => tick(el, run));
    }

    function onWheel(e: WheelEvent) {
      if (e.ctrlKey || e.metaKey || e.defaultPrevented || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      const dy = wheelPixels(e, window.innerHeight);
      if (dy === 0) return;
      const el = scrollerFor(e.target, dy);
      if (!el) return;
      e.preventDefault();
      let run = runs.get(el);
      if (!run) { run = { target: top(el), raf: 0, last: 0 }; runs.set(el, run); }
      if (!run.raf) run.target = top(el); // idle: start from where the page really is
      run.target = clampTarget(run.target + dy, max(el));
      if (!run.raf) { run.last = performance.now(); run.raf = requestAnimationFrame(() => tick(el, run!)); }
    }

    /** Keys, a scrollbar drag or a touch take over: stop easing so the two do not fight. */
    function stop() {
      for (const run of runs.values()) { cancelAnimationFrame(run.raf); run.raf = 0; }
    }

    window.addEventListener('wheel', onWheel, { passive: false });
    window.addEventListener('keydown', stop);
    window.addEventListener('pointerdown', stop);
    return () => {
      stop();
      window.removeEventListener('wheel', onWheel);
      window.removeEventListener('keydown', stop);
      window.removeEventListener('pointerdown', stop);
    };
  }, []);
  return null;
}
