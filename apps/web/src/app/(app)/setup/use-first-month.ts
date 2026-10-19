'use client';
import { useEffect, useRef, useState } from 'react';
import { api, errorText } from '@/lib/api';
import { fromPaise } from '@/common';
import type { PlanResponse } from '@/features/plan';
import type { Settings } from '@/features/setup';
import { useAmountField } from '@/lib/use-amount-field';

/** Step 4's fields: start from what the server holds and save on blur, on level change and on Finish. */
export function useFirstMonth(i: {
  settings: Settings | undefined; plan: PlanResponse | undefined; month: string | undefined;
  saveSettings: (patch: Partial<Settings>) => Promise<void>; savePlan: (p: PlanResponse) => Promise<unknown>;
}) {
  const opening = useAmountField();
  const plan = useAmountField();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const seeded = useRef({ opening: false, plan: false });

  useEffect(() => {
    if (i.settings && !seeded.current.opening) { seeded.current.opening = true; opening.setValue(fromPaise(i.settings.openingBalanceMinor)); }
  }, [i.settings]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (i.plan && !seeded.current.plan) { seeded.current.plan = true; plan.setValue(fromPaise(i.plan.totalMinor)); }
  }, [i.plan]); // eslint-disable-line react-hooks/exhaustive-deps

  /** Save what differs from the server. False when something failed (the error is shown). */
  async function flush(): Promise<boolean> {
    setBusy(true); setError('');
    try {
      if (i.settings && seeded.current.opening && opening.paise !== i.settings.openingBalanceMinor) await i.saveSettings({ openingBalanceMinor: opening.paise });
      if (i.plan && i.month && seeded.current.plan && plan.paise !== i.plan.totalMinor) {
        const res = await api.put<PlanResponse>(`/plans/${i.month}`, {
          totalMinor: plan.paise, lines: i.plan.lines.map((l) => ({ categoryId: l.categoryId, allocatedMinor: l.allocatedMinor })),
        });
        await i.savePlan(res);
      }
      return true;
    } catch (e) {
      setError(errorText(e, 'Could not save these numbers. Try again.'));
      return false;
    } finally { setBusy(false); }
  }

  async function setLevel(level: 70 | 80 | 90) {
    setError('');
    try { await i.saveSettings({ alertLevel: level }); } catch (e) { setError(errorText(e, 'Could not save the alert level. Try again.')); }
  }

  return { opening, plan, busy, error, flush, setLevel, ready: Boolean(i.settings && i.plan) };
}
