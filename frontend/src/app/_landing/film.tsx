'use client';
import { useEffect, useRef, useState } from 'react';
import s from './page.module.css';

const VIDEO = '/promo/videos/lbstash-story-1080p60.mp4';
const POSTER = '/promo/thumbnails/lbstash-story-poster.jpg';

/** The landing film: a muted loop, and "Watch with sound" plays the same file again with its soundtrack and controls.
 *  With "reduce motion" or "save data" on (and until the browser says otherwise), nothing loads until that button is pressed. */
export function HeroFilm() {
  const ref = useRef<HTMLVideoElement>(null);
  const [calm, setCalm] = useState(true);
  const [sound, setSound] = useState(false);

  useEffect(() => {
    const saveData = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection?.saveData;
    setCalm(Boolean(saveData) || window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }, []);

  // React does not reliably render the `muted` attribute, and browsers only autoplay muted video: set it on the element.
  useEffect(() => {
    const v = ref.current;
    if (!v) return;
    v.muted = !sound; v.loop = !sound; v.controls = sound;
    if (sound) v.currentTime = 0;
    if (sound || !calm) v.play().catch(() => {});
  }, [sound, calm]);

  const idle = calm && !sound;
  return (
    <figure className={s.film}>
      <video ref={ref} className={s.filmVideo} src={idle ? undefined : VIDEO} poster={POSTER} preload={idle ? 'none' : 'auto'} autoPlay={!calm} muted loop playsInline onEnded={() => setSound(false)} aria-label="A 45-second film of LBStash: log in Telegram, see where the month ends." />
      {!sound && <button type="button" className={`mono ${s.filmBtn}`} onClick={() => setSound(true)}>▶ Watch with sound</button>}
    </figure>
  );
}
