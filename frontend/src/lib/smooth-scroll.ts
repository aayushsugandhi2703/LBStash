/** Wheel smoothing maths. Pure: the component feeds it numbers and applies the result. */

const LINE_PX = 40;

/** A wheel event as pixels: browsers report lines (mice in Firefox) or pages as well. */
export function wheelPixels(e: { deltaY: number; deltaMode: number }, pageHeight: number): number {
  return e.deltaMode === 1 ? e.deltaY * LINE_PX : e.deltaMode === 2 ? e.deltaY * pageHeight : e.deltaY;
}

export const clampTarget = (target: number, max: number): number => Math.min(Math.max(0, max), Math.max(0, target));

/** Can this scroller still move in the direction of `dy` (negative = up)? An edge hands the wheel to the container outside it. */
export function canScroll(scrollTop: number, clientHeight: number, scrollHeight: number, dy: number): boolean {
  return dy < 0 ? scrollTop > 0 : scrollTop + clientHeight < scrollHeight - 1;
}

/** One frame of easing toward `target`: covers a share of the gap that depends on the frame time, so it looks the same at 60 and 120 Hz. Snaps when close. */
export function stepToward(current: number, target: number, dtMs: number, tauMs = 110): number {
  const gap = target - current;
  if (Math.abs(gap) < 0.5) return target;
  return current + gap * (1 - Math.exp(-Math.max(0, dtMs) / tauMs));
}
