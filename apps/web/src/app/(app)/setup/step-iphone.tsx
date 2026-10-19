'use client';
import { useEffect, useState } from 'react';
import type { z } from 'zod';
import type { DeviceTokenRes } from '@/contracts';
import { Button, ErrorLine, Field, TextLink } from '@/components/ui';
import { api, errorText } from '@/lib/api';
import type { Device } from '@/features/devices';
import { SHORTCUT_FILE, testReceived } from '@/features/setup';
import { Checkbox, CopyLink, Live, MirrorBox, Note, StepRow } from './parts';
import s from './page.module.css';

export type Ticks = Record<'a' | 'b' | 'c' | 'd', boolean>;

/** Step 1: connect the iPhone with a downloadable Shortcut. `token` is the plain token, held only in this visit's memory. */
export function StepIphone({ device, token, ticks, tick, onMade }: {
  device: Device | undefined; token: string; ticks: Ticks; tick: (k: keyof Ticks, v: boolean) => void; onMade: (token: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [origin, setOrigin] = useState('');
  const [bank, setBank] = useState('');
  const [localhost, setLocalhost] = useState(false);
  useEffect(() => {
    setOrigin(window.location.origin);
    setLocalhost(['localhost', '127.0.0.1'].includes(window.location.hostname));
    // the address the server is meant to be reached at (PUBLIC_URL), so the address below works from the phone
    fetch('/public-url').then((r) => (r.ok ? r.json() : null)).then((j: { url?: string } | null) => { if (j?.url) { setOrigin(j.url); setLocalhost(false); } }).catch(() => undefined);
  }, []);

  async function create() {
    setBusy(true); setError('');
    try {
      const r = await api.post<z.infer<typeof DeviceTokenRes>>('/devices', {});
      onMade(r.token);
      tick('a', true);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }

  const address = origin.replace(/\/$/, '');
  const tag = bank.trim() || '-BOB';
  const received = testReceived(device);

  return (
    <div className="rise">
      <StepRow n={1} title="Create your token" text="Lets your phone send messages, nothing else. You can cancel it any time." check={<Checkbox n={1} checked={ticks.a} onChange={(v) => tick('a', v)} />}>
        {!device && (
          <div className={s.control}>
            <Button disabled={busy} onClick={() => void create()}>Create token</Button>
            {error && <div className={s.err}><ErrorLine>{error}</ErrorLine></div>}
          </div>
        )}
        {device && token && (
          <>
            <div className={`${s.box} ${s.control}`}>
              <span className="mono" style={{ fontSize: 'var(--fs-s)', overflowWrap: 'anywhere' }}>{token}</span>
              <CopyLink value={token} />
            </div>
            <div className={`mono ${s.small} ${s.caption}`}>shown once · copy it now</div>
          </>
        )}
        {device && !token && (
          <>
            <div className={`${s.box} ${s.control}`}><span className="mono" style={{ fontSize: 'var(--fs-s)' }}>{device.tokenHint}</span></div>
            <div className={`mono ${s.small} ${s.caption}`}>
              not shown again · need a new one? <TextLink href="/account/devices" mono>Devices and Telegram</TextLink>
            </div>
          </>
        )}
      </StepRow>

      <StepRow
        n={2} title="Get the Shortcut"
        text="Tap Copy next to TOKEN. On your iPhone open this page, tap Download, then Add Shortcut. Keep the address and paste the token."
        check={<Checkbox n={2} checked={ticks.b} onChange={(v) => tick('b', v)} />}
      >
        <div className={s.control}><a className="btn" href={SHORTCUT_FILE} download>Download the Shortcut</a></div>
        <div className={s.fields}>
          <div className={s.field}><span className={`lbl ${s.k}`}>ADDRESS</span><span className={`mono ${s.v}`}>{address}</span><CopyLink value={address} /></div>
          <div className={s.field}>
            <span className={`lbl ${s.k}`}>TOKEN</span><span className={`mono ${s.v}`}>{token ? token : 'ledg_live_••••••••'}</span>
            {token ? <CopyLink value={token} /> : <span className={`mono ${s.small}`}>needs the token</span>}
          </div>
        </div>
        {localhost && <Note>Your phone cannot reach localhost. Open this page at your Mac&apos;s address instead.</Note>}
      </StepRow>

      <StepRow
        n={3} title="Make the automation"
        text={<>Shortcuts › Automation › + › <b>Message</b>. Next to <b>Message Contains</b> tap <b>Choose</b> and type your bank&apos;s tag. Next › <b>Run Shortcut › ledger-capture</b>, input <b>Shortcut Input</b>.</>}
        check={<Checkbox n={3} checked={ticks.c} onChange={(v) => tick('c', v)} />}
      >
        <div className={`${s.chips} ${s.control}`}>
          <span className={s.kw}><span className="mono" style={{ fontSize: 'var(--fs-s)' }}>{tag}</span><CopyLink chip value={tag} /></span>
        </div>
        <div className={s.control} style={{ maxWidth: 360 }}>
          <Field label="Your bank's tag" placeholder="-BOB" value={bank} onChange={(e) => setBank(e.target.value)} autoComplete="off" />
        </div>
        <Note>Use text from the message, like -BOB. A sender name like BOBSMS-S cannot be matched.</Note>
      </StepRow>

      <StepRow
        n={4} title="Run it immediately"
        text={<>Pick <b>Run Immediately</b>. Turn <b>Notify When Run</b> off. Choose <b>Always Allow</b> if asked. Tap Done.</>}
        check={<Checkbox n={4} checked={ticks.d} onChange={(v) => tick('d', v)} />}
      >
        <Note>A locked phone may run it late. That is fine.</Note>
      </StepRow>

      <StepRow
        n={5} title="Send a test"
        text={<><b>Lock your phone</b> and text yourself a line with your tag, like <span className="mono">Rs 1.00 Dr. from A/C test -BOB</span>. This page shows when it arrives.</>}
        check={<MirrorBox on={received !== null} />}
      >
        {received
          ? <Live kind="ok">{received}</Live>
          : <Live kind="wait">{device ? 'waiting for your first message…' : 'make the token first, then send the test'}</Live>}
        <Note>Not arriving? Same Wi-Fi, Mac awake. Open the address above in Safari on the phone, and allow Shortcuts under Settings › Privacy &amp; Security › Local Network.</Note>
      </StepRow>
    </div>
  );
}
