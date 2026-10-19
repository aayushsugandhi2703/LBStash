'use client';
import { useEffect, useState } from 'react';
import type { z } from 'zod';
import type { DeviceTokenRes } from '@/contracts';
import { Button, ErrorLine, TextLink } from '@/components/ui';
import { api, errorText } from '@/lib/api';
import type { Device } from '@/features/devices';
import { authHeader, BODY_LINES, HEADER_MASKED, ingestUrl, testReceived } from '@/features/setup';
import { Checkbox, CopyLink, Live, MirrorBox, Note, StepRow } from './parts';
import s from './page.module.css';

export type Ticks = Record<'a' | 'b' | 'c' | 'd' | 'e', boolean>;

/** Step 1: the six rows that connect the iPhone Shortcut. `token` is the plain token, held only in this visit's memory. */
export function StepIphone({ device, token, ticks, tick, onMade }: {
  device: Device | undefined; token: string; ticks: Ticks; tick: (k: keyof Ticks, v: boolean) => void; onMade: (token: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [origin, setOrigin] = useState('');
  useEffect(() => setOrigin(window.location.origin), []);

  async function create() {
    setBusy(true); setError('');
    try {
      const r = await api.post<z.infer<typeof DeviceTokenRes>>('/devices', {});
      onMade(r.token);
      tick('a', true);
    } catch (e) { setError(errorText(e)); } finally { setBusy(false); }
  }

  const url = ingestUrl(origin);
  const received = testReceived(device);

  return (
    <div className="rise">
      <StepRow n={1} title="Create your ingest token" text="A secret that lets your phone send messages and nothing else. It cannot read your data, and you can cancel it any time." check={<Checkbox n={1} checked={ticks.a} onChange={(v) => tick('a', v)} />}>
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
            <div className={`mono ${s.small} ${s.caption}`}>shown once, copy it now · lose it and you simply make a new one</div>
          </>
        )}
        {device && !token && (
          <>
            <div className={`${s.box} ${s.control}`}><span className="mono" style={{ fontSize: 'var(--fs-s)' }}>{device.tokenHint}</span></div>
            <div className={`mono ${s.small} ${s.caption}`}>
              a token exists and is never shown again · to see a new one, <TextLink href="/account/devices" mono>make one under Devices and Telegram</TextLink>
            </div>
          </>
        )}
      </StepRow>

      <StepRow n={2} title="Open Shortcuts and start an automation" text="On your iPhone open the Shortcuts app, then go through these screens." check={<Checkbox n={2} checked={ticks.b} onChange={(v) => tick('b', v)} />}>
        <div className={`mono ${s.path} ${s.control}`} style={{ fontSize: 'var(--fs-s)' }}>Shortcuts › Automation › New Automation › Message</div>
      </StepRow>

      <StepRow n={3} title="Set the trigger: Message Contains" text="Make one automation per word. Your bank may phrase things differently, so check a real message and add that word too." check={<Checkbox n={3} checked={ticks.c} onChange={(v) => tick('c', v)} />}>
        <div className={`${s.chips} ${s.control}`}>
          {['debited', 'credited'].map((w) => (
            <span key={w} className={s.kw}><span className="mono" style={{ fontSize: 'var(--fs-s)' }}>{w}</span><CopyLink chip value={w} /></span>
          ))}
        </div>
        <Note>Never trigger on every message from the bank. Banks also text OTPs, and an OTP must never leave your phone.</Note>
      </StepRow>

      <StepRow
        n={4} title="Add the action: Get Contents of URL"
        text="Fill it in exactly like this. First add a Dictionary action with the three fields below, then this action with Request Body set to JSON and that Dictionary as its value. Your shortcut should have only these two actions: fewer steps run more reliably on a locked phone."
        check={<Checkbox n={4} checked={ticks.d} onChange={(v) => tick('d', v)} />}
      >
        <div className={s.fields}>
          <div className={s.field}><span className={`lbl ${s.k}`}>URL</span><span className={`mono ${s.v}`}>{url}</span><CopyLink value={url} /></div>
          <div className={s.field}><span className={`lbl ${s.k}`}>METHOD</span><span className={`mono ${s.v}`}>POST</span></div>
          <div className={s.field}>
            <span className={`lbl ${s.k}`}>HEADER</span><span className={`mono ${s.v}`}>{HEADER_MASKED}</span>
            {token ? <CopyLink value={authHeader(token)} /> : <span className={`mono ${s.small}`}>needs the token</span>}
          </div>
          <div className={s.field} data-top="true">
            <span className={`lbl ${s.k}`}>BODY</span><span className={`mono ${s.v} ${s.wrap}`}>{BODY_LINES.map((l) => <span key={l} style={{ display: 'block' }}>{l}</span>)}</span>
            <CopyLink value={BODY_LINES.join('\n')} />
          </div>
        </div>
      </StepRow>

      <StepRow
        n={5} title="Run it immediately, silently"
        text={<>Pick <b>Run Immediately</b> (not Ask Before Running) and turn <b>Notify When Run</b> off. If your iOS offers a run-while-locked setting for the shortcut, turn it on. Tap Done. Repeat for the second word.</>}
        check={<Checkbox n={5} checked={ticks.e} onChange={(v) => tick('e', v)} />}
      >
        <Note>iPhone may run it late while locked. That is fine: each payment is saved at the time written in the bank message, and a balance check later catches anything that never arrives.</Note>
      </StepRow>

      <StepRow
        n={6} title="Send a test"
        text={<><b>Lock your phone first</b>, then ask someone to text you <span className="mono">Rs 1.00 debited test</span>, or just wait for your next bank alert. This page will notice and show how long it took.</>}
        check={<MirrorBox on={received !== null} />}
      >
        {received
          ? <Live kind="ok">{received}</Live>
          : <Live kind="wait">{device ? 'waiting for your first message…' : 'make the token first, then send the test'}</Live>}
      </StepRow>
    </div>
  );
}
