'use client';
import { ErrorLine, TallyMath, Loading, Segmented } from '@/components/ui';
import { LEVELS } from '@/features/limits';
import { alertText, money, type Settings } from '@/features/setup';
import type { useFirstMonth } from './use-first-month';
import s from './page.module.css';

type Fields = ReturnType<typeof useFirstMonth>;

/** Step 3: opening balance, money to plan, alert level, with the arithmetic under them. The balance is a position, so it is ink. */
export function StepFirstMonth({ f, settings }: { f: Fields; settings: Settings | undefined }) {
  if (!f.ready || !settings) return <Loading />;
  return (
    <div className={`rise ${s.first}`}>
      <div>
        <label htmlFor="opening" className="lbl">OPENING BALANCE · YOUR BANK TODAY</label>
        <div className={s.rupee}><span aria-hidden="true">₹</span><input id="opening" type="text" placeholder="0" {...f.opening.inputProps} onBlur={() => void f.flush()} /></div>
        <div className={`cap ${s.help}`}>The account your bank messages come from.</div>
      </div>
      <div>
        <label htmlFor="plan" className="lbl">MONEY TO PLAN THIS MONTH</label>
        <div className={s.rupee}><span aria-hidden="true">₹</span><input id="plan" type="text" placeholder="0" {...f.plan.inputProps} onBlur={() => void f.flush()} /></div>
        <div className={`cap ${s.help}`}>Split it into categories later, on Budget.</div>
      </div>
      <div>
        <div className="lbl" style={{ marginBottom: 8 }}>WARN ME AT</div>
        <Segmented label="Alert level" value={String(settings.alertLevel)} options={LEVELS.map((l) => ({ value: String(l.level), label: `${l.level}%` }))} onChange={(v) => void f.setLevel(Number(v) as 70 | 80 | 90)} />
      </div>
      <div className={s.firstMath}>
        <TallyMath
          rows={[{ k: 'opening balance', v: money(f.opening.value) }, { k: 'to plan this month', v: money(f.plan.value) }]}
          total={{ k: '= alerts at', v: <span className={s.ink}>{alertText(settings.alertLevel)}</span> }}
        />
      </div>
      {f.error && <ErrorLine>{f.error}</ErrorLine>}
    </div>
  );
}
