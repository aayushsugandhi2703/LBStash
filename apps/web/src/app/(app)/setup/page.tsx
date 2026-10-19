'use client';
import { useEffect, useState } from 'react';
import { AppShell } from '@/components/shell';
import { Button, ErrorLine, IndexList, LedgerMath } from '@/components/ui';
import { api, errorText, useApi } from '@/lib/api';
import { useToday } from '@/lib/me';
import { fromPaise } from '@/common';
import { type Device, ingestState, type LinkStatus, type TgSettings } from '@/features/devices';
import type { PlanResponse } from '@/features/plan';
import { clampStep, nextLabel, phoneHeard, type Settings, type Step, stepLabel, stepLead, STEPS, stepStates, stepTitle, summaryRows } from '@/features/setup';
import { StepDone } from './step-done';
import { StepFirstMonth } from './step-first-month';
import { StepIphone, type Ticks } from './step-iphone';
import { StepPrivacy } from './step-privacy';
import { StepTelegram } from './step-telegram';
import { useFirstMonth } from './use-first-month';
import s from './page.module.css';

/** The furthest step reached is a per-browser convenience: it only decides whether steps 3 and 4 read done. */
const REACHED_KEY = 'ledger.setup.reached';

function readReached(): Step {
  try { return clampStep(Number(window.localStorage.getItem(REACHED_KEY) ?? 1)); } catch { return 1; }
}
function writeReached(step: Step): void {
  try { window.localStorage.setItem(REACHED_KEY, String(step)); } catch { /* private window: the guide still works */ }
}

export default function SetupPage() {
  const [step, setStep] = useState<Step>(1);
  const [reached, setReached] = useState<Step>(1);
  const [token, setToken] = useState('');
  const [ticks, setTicks] = useState<Ticks>({ a: false, b: false, c: false, d: false, e: false });
  const [privacyError, setPrivacyError] = useState('');

  const today = useToday();
  const month = today?.month;
  const devices = useApi<{ devices: Device[] }>('/devices');
  const link = useApi<LinkStatus>('/telegram/link');
  const settings = useApi<Settings>('/settings');
  const plan = useApi<PlanResponse>(month ? `/plans/${month}` : null);

  useEffect(() => setReached(readReached()), []);
  const go = (n: number) => {
    const next = clampStep(n);
    setStep(next);
    setReached((r) => { const m = Math.max(r, next) as Step; writeReached(m); return m; });
  };

  const ingest = ingestState(devices.data?.devices ?? []);
  const device = ingest.kind === 'live' ? ingest.device : undefined;
  const heard = phoneHeard(device);
  const signed = Boolean(link.data?.sessionActive);
  const states = stepStates({
    step, reached, token: ingest.kind === 'live', test: heard,
    botSaved: Boolean(link.data?.botSaved), linked: Boolean(link.data?.linked), signed,
  });

  // The page notices the phone's first message and the Telegram link and sign-in on its own.
  const watchPhone = step === 1 && Boolean(device) && !heard;
  const watchBot = step === 2 && !states.done[1];
  useEffect(() => {
    if (!watchPhone) return;
    const t = window.setInterval(() => void devices.mutate(), 4000);
    return () => window.clearInterval(t);
  }, [watchPhone]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!watchBot) return;
    const t = window.setInterval(() => void link.mutate(), 3000);
    return () => window.clearInterval(t);
  }, [watchBot]); // eslint-disable-line react-hooks/exhaustive-deps

  /** PATCH /settings with the change shown at once; a refused change rolls back and the caller says so. */
  async function saveSettings(patch: Partial<Settings>): Promise<void> {
    await settings.mutate(api.patch<Settings>('/settings', patch), {
      optimisticData: (cur) => (cur ? { ...cur, ...patch } : (cur as unknown as Settings)),
      rollbackOnError: true, populateCache: true, revalidate: false,
    });
  }
  async function saveTelegram(patch: Partial<TgSettings>): Promise<void> {
    setPrivacyError('');
    try { await saveSettings(patch); } catch (e) { setPrivacyError(errorText(e, 'Could not save that. Try again.')); }
  }

  const first = useFirstMonth({
    settings: settings.data, plan: plan.data, month, saveSettings, savePlan: (p) => plan.mutate(p, { revalidate: false }),
  });

  async function next() {
    if (step === 4 && !(await first.flush())) return;
    go(step + 1);
  }

  const summary = summaryRows({
    s1: states.done[0], s2: states.done[1], link: link.data, settings: settings.data,
    opening: settings.data ? fromPaise(settings.data.openingBalanceMinor) : '', plan: plan.data ? fromPaise(plan.data.totalMinor) : '',
  });

  const aside = (
    <>
      <div className={`lbl ${s.blockHead}`}>Four steps</div>
      <IndexList
        label="Setup steps"
        items={STEPS.map((st, i) => ({
          key: st.label, label: st.label, active: step === i + 1, onClick: () => go(i + 1),
          value: <span className={s.state} data-done={states.words[i] === 'done'}>{states.words[i]}</span>,
        }))}
      />
      <div className={`opt2 ${s.arith}`}>
        <LedgerMath
          rows={[{ k: 'account secured', v: 'yes', tone: 'credit' }, { k: 'steps done', v: `${states.count} of 4` }]}
          total={{ k: '= still to do', v: <span className={s.ink}>{states.left}</span> }}
        />
      </div>
    </>
  );

  return (
    <AppShell home={null} glyph="setup" title="Setup guide" description="Four steps so your bank messages flow into the ledger on their own. About 15 minutes, once." aside={aside}>
      <div className={s.head}>
        <div className="lbl">{stepLabel(step)}</div>
        <h2 className={`fig-lg ${s.title}`}>{stepTitle(step)}</h2>
        <p className={`cap ${s.lead}`}>{stepLead(step)}</p>
      </div>

      <div className={s.body}>
        {step === 1 && (
          devices.error && !devices.data
            ? <LoadFailed what="your devices" retry={() => void devices.mutate()} />
            : <StepIphone device={device} token={token} ticks={ticks} tick={(k, v) => setTicks((t) => ({ ...t, [k]: v }))} onMade={(t) => { setToken(t); void devices.mutate(); }} />
        )}
        {step === 2 && (
          link.data
            ? <StepTelegram link={link.data} refresh={() => void link.mutate()} />
            : link.error ? <LoadFailed what="the Telegram link" retry={() => void link.mutate()} /> : null
        )}
        {step === 3 && <StepPrivacy settings={settings.data} failed={Boolean(settings.error)} error={privacyError} save={(p) => void saveTelegram(p)} retry={() => void settings.mutate()} />}
        {step === 4 && (
          !first.ready && (settings.error || plan.error)
            ? <LoadFailed what="your balance and plan" retry={() => { void settings.mutate(); void plan.mutate(); }} />
            : <StepFirstMonth f={first} settings={settings.data} />
        )}
        {step === 5 && <StepDone rows={summary} />}
      </div>

      {step < 5 && (
        <div className={s.foot}>
          <Button large disabled={first.busy} onClick={() => void next()}>{nextLabel(step)}</Button>
          <button type="button" className={s.quiet} onClick={() => go(step - 1)}>Back</button>
          <button type="button" className={s.quiet} onClick={() => void next()}>Skip for now</button>
        </div>
      )}
    </AppShell>
  );
}

function LoadFailed({ what, retry }: { what: string; retry: () => void }) {
  return (
    <div style={{ padding: 'var(--row-pad) 0' }}>
      <ErrorLine>{`Could not read ${what}. Nothing was changed.`}</ErrorLine>
      <button type="button" className="link mono" style={{ marginTop: 6 }} onClick={retry}>Try again</button>
    </div>
  );
}
