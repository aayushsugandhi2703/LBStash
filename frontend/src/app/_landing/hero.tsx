'use client';
import { useState } from 'react';
import Link from 'next/link';
import { formatInr } from '@/common';
import { bars, LOGGED_DAYS, MONTH_DAYS, scrub } from '@/features/month';
import { DemoButton } from './demo-button';
import s from './page.module.css';

/** The top of the About page: "It's day N." and a slider that walks through a sample month. */
export function Hero() {
  const [day, setDay] = useState(LOGGED_DAYS);
  const v = scrub(day);
  const columns = bars(day);

  return (
    <section className={`${s.hero} ${s.wrap}`} aria-labelledby="hero-h">
      <div className={s.eyebrow}>
        <span className="lbl">A private budget tracker</span>
        <span className={`lbl ${s.hint}`}>Drag the slider. It is a sample month.</span>
      </div>
      <h1 id="hero-h" className={s.h1}>It’s day <span className={s.dayNum}>{day}</span>.<br /><span className={s.soft}>Where’s your month going?</span></h1>

      <div className={s.heroRow}>
        <p className={s.lead}>LBStash takes what you log in Telegram and tells you where the month ends, <b>before it ends</b>. Scrub through a sample month below to see what it sees.</p>
        <div className={s.actions}>
          <DemoButton className={s.bigBtn} />
          <Link href="/create-account" className={`ghost ${s.bigGhost}`}>Create account</Link>
        </div>
      </div>
      <p className={`cap ${s.note}`}>The demo has sample data and is read-only. No sign-up needed.</p>

      <div className={s.scrub} role="group" aria-label="A sample month. Move the slider to change the day.">
        <div className={s.scrubL}>
          <div className={s.scrubHead}>
            <span className="lbl">Flexible spending per day · sample data</span>
            <span className="lbl"><span className={s.keySq} aria-hidden="true" />a repeat leaves</span>
          </div>
          <div className={s.bars} role="img" aria-label={`Spending per day in a sample month. Solid bars are logged, striped bars are forecast. Day ${day} is highlighted.`}>
            {columns.map((b) => (
              <div key={b.day} className={s.bcol}>
                <span className={s.mk} data-on={b.repeat} />
                <span className={s.bar} data-kind={b.kind} data-state={b.state} style={{ height: `${b.heightPct * 0.74 + 6}%` }} />
              </div>
            ))}
          </div>
          <div className={`mono ${s.dlabels}`} aria-hidden="true">{columns.map((b) => <span key={b.day}>{b.label}</span>)}</div>
          <label htmlFor="day" className="sr">Day of the month</label>
          <input
            id="day" className={s.range} type="range" min={1} max={MONTH_DAYS} step={1} value={day}
            aria-valuetext={`Day ${day}, ${v.phase}`} onChange={(e) => setDay(Number(e.target.value))}
          />
          <div className={s.jump}>
            <button type="button" onClick={() => setDay(1)}>Day 1</button>
            <button type="button" onClick={() => setDay(LOGGED_DAYS)}>Today · {LOGGED_DAYS}</button>
            <button type="button" onClick={() => setDay(MONTH_DAYS)}>Month end · {MONTH_DAYS}</button>
          </div>
        </div>
        <div className={s.scrubR} aria-live="polite">
          <div className={`lbl ${s.readHead}`}>Day {day} · {v.phase}</div>
          <div className={s.rd}><div className="lbl">Available to you</div><div className={s.rdV}>₹{formatInr(v.availableMinor)}</div></div>
          <div className={s.rd}><div className="lbl">Flexible spent / plan {formatInr(v.planMinor)}</div><div className={`${s.rdV} ${s.sm}`}>₹{formatInr(v.spentMinor)}</div></div>
          <div className={s.verdict} data-tone={v.verdict.tone}><i aria-hidden="true" /><span>{v.verdict.text}</span></div>
        </div>
      </div>
    </section>
  );
}
