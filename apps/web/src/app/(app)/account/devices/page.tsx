'use client';
import { useState } from 'react';
import Link from 'next/link';
import type { z } from 'zod';
import type { BalanceChecksRes, DeviceTokenRes, TransactionPageDto, SettingsDto } from '@/contracts';
import { AccountShell } from '@/components/shell';
import { Button, CodeInput, ErrorLine, GhostButton, GhostLink, TallyMath, Loading, Segmented, SettingsRow, StatusLine, Switch, TextLink } from '@/components/ui';
import { api, errorText, useApi } from '@/lib/api';
import { inrSigned } from '@/common';
import { codeError, isCode } from '@/features/account';
import { AFTER_OPTIONS, balanceView, type Device, DIGEST_OPTIONS, IDLE_OPTIONS, ingestState, type LinkStatus, receiveLead, receiveTitle, sessionLead, tgMeta, type TgSettings, tgShort, tgState, tokenLine } from '@/features/devices';
import { copyToClipboard, useFlash } from '@/lib/browser';
import { LoadError, Section, Sq, Well } from '../parts';
import s from '../account.module.css';

type Settings = z.infer<typeof SettingsDto>;
type Test = 'idle' | 'waiting' | 'done' | 'error';
type Ask = '' | 'rotate' | 'cancel';
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

export default function DevicesPage() {
  const devices = useApi<{ devices: Device[] }>('/devices', { refreshInterval: 15_000 });
  const link = useApi<LinkStatus>('/telegram/link', { refreshInterval: 15_000 });
  const settings = useApi<Settings>('/settings');
  const transactions = useApi<z.infer<typeof TransactionPageDto>>('/transactions?limit=1');
  const checks = useApi<z.infer<typeof BalanceChecksRes>>('/balance-checks?limit=1');

  const ingest = ingestState(devices.data?.devices ?? []);
  const tg = tgState(link.data);
  const bank = balanceView(checks.data?.items[0]);
  const live = ingest.kind === 'live';

  return (
    <AccountShell
      page="devices" glyph="devices" title="Devices and Telegram"
      description="Where bank messages come in and prompts go out."
      label="DEVICES" heading="Capture and the bot"
      lead="Log payments in Telegram with /350 food. An optional token lets another tool send bank messages in."
      summary={<TallyMath rows={[
        { k: 'token', v: devices.data ? (live ? 'receiving' : ingest.kind === 'none' ? 'no token' : 'not receiving') : '—' },
        { k: 'telegram', v: link.data ? tgShort(tg) : '—' },
        { k: 'balance', v: checks.data ? bank.short : '—' },
      ]} total={{ k: '= capture', v: devices.data ? (live ? 'working' : 'stopped') : '—' }} />}
    >
      <Section first>BANK MESSAGE TOKEN (OPTIONAL)</Section>
      {devices.error && !devices.data && <LoadError retry={() => void devices.mutate()} />}
      {!devices.data && !devices.error && <Loading />}
      {devices.data && <IphoneBlock devices={devices.data.devices} refresh={() => void devices.mutate()} />}

      <Section>TELEGRAM</Section>
      {link.error && !link.data && <LoadError retry={() => void link.mutate()} />}
      {!link.data && !link.error && <Loading />}
      {link.data && <TelegramBlock link={link.data} settings={settings.data} refresh={() => void link.mutate()} saveSettings={(p) => saveSettings(settings, p)} settingsFailed={Boolean(settings.error) && !settings.data} retrySettings={() => void settings.mutate()} />}

      <Section>BANK ACCOUNT AND BALANCE</Section>
      <SettingsRow title="Tracked account" sub="one account is tracked in this version" mono>
        <span className={`mono ${s.mono13}`}>{transactions.data ? `${inrSigned(transactions.data.balanceMinor)} in the transactions` : '—'}</span>
      </SettingsRow>
      <div className={s.lineRow}>
        <span className={s.lead}>
          <Sq kind={bank.kind === 'wait' ? 'wait' : bank.kind === 'none' ? 'wait' : 'ok'} />
          <span><span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>Last balance check</span><span className={`mono ${s.mono11}`} style={{ display: 'block', marginTop: 2, lineHeight: 1.5 }}>{checks.data ? bank.text : checks.error ? 'could not read the last check' : 'loading…'}</span></span>
        </span>
        <GhostLink href="/transactions?check=1">Check now</GhostLink>
      </div>
      <SettingsRow title="Wait before booking a gap" sub="Wait this long for a late message before booking the gap as Unaccounted.">
        <span className={`mono ${s.mono13}`}>{settings.data ? `${settings.data.reconcileGraceHours} ${settings.data.reconcileGraceHours === 1 ? 'hour' : 'hours'}` : '—'}</span>
      </SettingsRow>
    </AccountShell>
  );
}

/** PATCH /settings with the change shown at once; a refused change rolls back and says so. */
async function saveSettings(settings: { mutate: ReturnType<typeof useApi<Settings>>['mutate'] }, patch: Partial<TgSettings>): Promise<void> {
  await settings.mutate(api.patch<Settings>('/settings', patch), {
    optimisticData: (cur) => (cur ? { ...cur, ...patch } : (cur as unknown as Settings)),
    rollbackOnError: true, populateCache: true, revalidate: false,
  });
}


function IphoneBlock({ devices, refresh }: { devices: Device[]; refresh: () => void }) {
  const ing = ingestState(devices);
  const dev = ing.kind === 'none' ? undefined : ing.device;
  const [test, setTest] = useState<Test>('idle');
  const [testError, setTestError] = useState('');
  const [ask, setAsk] = useState<Ask>('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [newToken, setNewToken] = useState('');
  const [flags, flash] = useFlash();

  async function sendTest() {
    setTest('waiting'); setTestError('');
    try {
      await Promise.all([api.post('/devices/test'), sleep(900)]);
      setTest('done'); refresh();
    } catch (e) { setTest('error'); setTestError(errorText(e)); }
  }
  const toggle = (which: Exclude<Ask, ''>) => { setAsk(ask === which ? '' : which); setCode(''); setError(''); setNewToken(''); };
  async function rotate() {
    if (!dev) return;
    setBusy(true); setError('');
    try {
      const r = await api.post<z.infer<typeof DeviceTokenRes>>('/devices', { deviceId: dev.id, code });
      setNewToken(r.token); setAsk(''); setCode(''); refresh();
    } catch (e) { setError(codeError(e) ?? errorText(e)); setCode(''); } finally { setBusy(false); }
  }
  async function create() {
    setBusy(true); setError('');
    try {
      const r = await api.post<z.infer<typeof DeviceTokenRes>>('/devices', {});
      setNewToken(r.token); refresh();
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  async function cancel() {
    if (!dev) return;
    setBusy(true); setError('');
    try {
      await api.del(`/devices/${dev.id}`, { code });
      setAsk(''); setCode(''); setNewToken(''); refresh();
    } catch (e) { setError(codeError(e) ?? errorText(e)); setCode(''); } finally { setBusy(false); }
  }

  return (
    <>
      <div className={s.lineRow}>
        <span className={s.lead}>
          <Sq kind={ing.kind === 'live' ? 'ok' : 'stop'} />
          <span>
            <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>{receiveTitle(ing)}</span>
            <span className={`mono ${s.mono11}`} style={{ display: 'block', marginTop: 2, lineHeight: 1.5 }}>{receiveLead(ing)}</span>
          </span>
        </span>
        <GhostButton disabled={ing.kind !== 'live' || test === 'waiting'} onClick={() => void sendTest()}>Send a test message</GhostButton>
      </div>
      {test === 'waiting' && <div className={s.line}><StatusLine kind="wait"><span className="mono">waiting for the test message…</span></StatusLine></div>}
      {test === 'done' && <div className={`rise ${s.line}`}><StatusLine>Test message received and read. It was not added to your transactions.</StatusLine></div>}
      {test === 'error' && <div className={s.line}><ErrorLine>{testError}</ErrorLine></div>}

      <div className={s.lineRow}>
        <span className={s.min0}>
          <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>Ingest token</span>
          <span className={`mono ${s.mono11}`} style={{ display: 'block', marginTop: 2, lineHeight: 1.5 }}>{tokenLine(ing)}</span>
        </span>
        {ing.kind === 'live' && (
          <span className={s.btns}>
            <GhostButton onClick={() => toggle('rotate')}>{ask === 'rotate' ? 'Cancel' : 'Make a new token'}</GhostButton>
            <GhostButton bad onClick={() => toggle('cancel')}>{ask === 'cancel' ? 'Back' : 'Cancel token'}</GhostButton>
          </span>
        )}
      </div>
      <div className={s.rowNote}>The token can only send messages in. It cannot read anything.</div>
      {ask === 'rotate' && (
        <Well>
          <p>The old token stops at once. Give the new one to whatever sends your bank messages.</p>
          <div className="actions">
            <CodeInput value={code} onChange={(v) => { setCode(v); setError(''); }} />
            <Button disabled={!isCode(code) || busy} onClick={() => void rotate()}>Make a new token</Button>
            {error && <div className={s.full}><ErrorLine>{error}</ErrorLine></div>}
          </div>
        </Well>
      )}
      {newToken && (
        <div role="status" className="well" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '12px 16px', marginTop: 'var(--row-pad)' }}>
          <span className={`mono ${s.token}`}>{newToken}</span>
          <TextLink mono onClick={() => void copyToClipboard(newToken).then((ok) => ok && flash('token'))}>{flags.token ? 'Copied' : 'Copy'}</TextLink>
          <span className={`mono ${s.mono11}`} style={{ flexBasis: '100%' }}>shown once · copy it now</span>
        </div>
      )}
      {ask === 'cancel' && (
        <Well>
          <p>For a lost or leaked token. Bank messages stop until you make a new one.</p>
          <div className="actions">
            <CodeInput value={code} onChange={(v) => { setCode(v); setError(''); }} />
            <GhostButton bad disabled={!isCode(code) || busy} onClick={() => void cancel()}>Cancel the token</GhostButton>
            {error && <div className={s.full}><ErrorLine>{error}</ErrorLine></div>}
          </div>
        </Well>
      )}
      {ing.kind === 'gone' && (
        <div role="status" className={`rise ${s.lineRow}`}>
          <span className={s.lead}><Sq kind="stop" /><span className={s.red} style={{ fontSize: 'var(--fs-s)' }}>Token cancelled. Nothing can send bank messages with it any more.</span></span>
          <Button disabled={busy} onClick={() => void create()}>Make a new token</Button>
        </div>
      )}
      {ing.kind === 'none' && (
        <div role="status" className={s.lineRow}>
          <span className={s.lead}><Sq kind="stop" /><span style={{ fontSize: 'var(--fs-s)' }}>No token yet. Only needed if another tool will send bank messages in.</span></span>
          <Button disabled={busy} onClick={() => void create()}>Make a token</Button>
        </div>
      )}
      <div className={s.line}><TextLink href="/setup" mono>Run the Setup guide again →</TextLink></div>
    </>
  );
}


function TelegramBlock({ link, settings, refresh, saveSettings: save, settingsFailed, retrySettings }: {
  link: LinkStatus; settings: Settings | undefined; refresh: () => void; saveSettings: (p: Partial<TgSettings>) => Promise<void>; settingsFailed: boolean; retrySettings: () => void;
}) {
  const tg = tgState(link);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true); setError('');
    try { await fn(); refresh(); } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }
  const change = async (p: Partial<TgSettings>) => { setError(''); try { await save(p); } catch (e) { setError(errorText(e)); } };

  return (
    <>
      <div className={s.lineRow}>
        <span className={s.min0}>
          <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>{tg.kind === 'unlinked' ? 'Not linked' : 'Linked to your Telegram'}</span>
          <span className={`mono ${s.mono11}`} style={{ display: 'block', marginTop: 2, lineHeight: 1.5 }}>{tgMeta(link)}</span>
        </span>
        {tg.kind === 'unlinked'
          ? <Link href="/setup" className="btn">Open the Setup guide</Link>
          : <GhostButton bad disabled={busy} onClick={() => void run(() => api.del('/telegram/link'))}>Unlink</GhostButton>}
      </div>
      {error && <ErrorLine>{error}</ErrorLine>}

      {tg.kind !== 'unlinked' && (
        <>
          <div className={s.lineRow}>
            <span className={s.lead}>
              <Sq kind={tg.kind === 'in' ? 'ok' : 'wait'} />
              <span>
                <span style={{ display: 'block', fontSize: 'var(--fs-body)', fontWeight: 500 }}>{tg.kind === 'in' ? 'Signed in to the bot' : 'Signed out of the bot'}</span>
                <span className="cap" style={{ display: 'block', marginTop: 2 }}>{sessionLead(link)}</span>
              </span>
            </span>
            {tg.kind === 'in'
              ? <GhostButton disabled={busy} onClick={() => void run(() => api.del('/telegram/session'))}>Sign out of the bot</GhostButton>
              : link.botUsername
                ? <a className="ghost" href={`https://t.me/${link.botUsername}`} target="_blank" rel="noopener noreferrer">Send /signin in Telegram</a>
                : <span className={`mono ${s.mono11}`}>send /signin in Telegram</span>}
          </div>

          {settingsFailed && <LoadError retry={retrySettings}>Could not read the bot settings.</LoadError>}
          {!settings && !settingsFailed && <Loading />}
          {settings && (
            <>
              <SettingsRow title="Show a Reveal button" sub="Shows amount and payee for 30 seconds, through Telegram. Off: Telegram sees no bank detail.">
                <Switch checked={settings.allowReveal} label="Show a Reveal button" onChange={(v) => void change({ allowReveal: v })} />
              </SettingsRow>
              <div className={s.segBlock}>
                <div className="lbl">ALSO SIGN ME OUT OF THE BOT AFTER</div>
                <Segmented label="Idle days" value={String(settings.sessionIdleDays)} options={IDLE_OPTIONS.map((o) => ({ value: String(o.value), label: o.label }))} onChange={(v) => void change({ sessionIdleDays: Number(v) })} />
                <div className={`cap ${s.segNote}`}>Otherwise you stay signed in until /signout.</div>
              </div>
              <div className={s.segBlock}>
                <div className="lbl">DAILY REMINDER OF UNTAGGED PAYMENTS</div>
                <Segmented label="Digest" value={settings.digestMode} options={DIGEST_OPTIONS} onChange={(v) => void change({ digestMode: v })} />
              </div>
              <div className={s.segBlock}>
                <div className="lbl">AFTER YOU TAG A PAYMENT</div>
                <Segmented label="After tagging" value={settings.afterTag} options={AFTER_OPTIONS} onChange={(v) => void change({ afterTag: v })} />
              </div>
            </>
          )}
        </>
      )}
      {tg.kind === 'unlinked' && <div className={`rise ${s.pausedNote}`}>Prompts are paused. Link the bot again from the Setup guide.</div>}
    </>
  );
}
