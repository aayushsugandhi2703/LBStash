'use client';
import { useEffect, useState } from 'react';
import type { PairingRes } from '@/contracts';
import { Button, ErrorLine, Field } from '@/components/ui';
import { api, errorText, fieldErrors } from '@/lib/api';
import { countdown, type LinkStatus } from '@/features/devices';
import { canSaveBot, linkedText, signWaitText } from '@/features/setup';
import { CopyLink, Live, StepRow } from './parts';
import s from './page.module.css';

const mono = (t: string) => <span className="mono">{t}</span>;

/** Step 2: own bot, token, link code, sign-in. Everything shown is read from `GET /telegram/link` (polled by the page). */
export function StepTelegram({ link, refresh }: { link: LinkStatus; refresh: () => void }) {
  const [botToken, setBotToken] = useState('');
  const [replacing, setReplacing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [pairing, setPairing] = useState<PairingRes | null>(null);
  const [pairBusy, setPairBusy] = useState(false);
  const [pairError, setPairError] = useState('');
  const [now, setNow] = useState(() => Date.now());

  // the 5-minute code counts down once a second while it is on screen
  useEffect(() => {
    if (!pairing || link.linked) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [pairing, link.linked]);

  async function saveBot() {
    setSaving(true); setSaveError('');
    try {
      await api.post('/telegram/bot-token', { token: botToken.trim() });
      setBotToken(''); setReplacing(false); setPairing(null);
      refresh();
    } catch (e) { setSaveError(Object.values(fieldErrors(e))[0] ?? errorText(e)); } finally { setSaving(false); }
  }
  async function makeCode() {
    setPairBusy(true); setPairError('');
    try {
      setPairing(await api.post<PairingRes>('/telegram/pairing'));
      setNow(Date.now());
      refresh();
    } catch (e) { setPairError(errorText(e)); } finally { setPairBusy(false); }
  }

  const leftMs = pairing ? new Date(pairing.expiresAt).getTime() - now : 0;
  const code = pairing && leftMs > 0 ? pairing : null;
  const asking = !link.botSaved || replacing;

  return (
    <div className="rise">
      <StepRow n={1} title="Create your own bot" text={<>In Telegram open {mono('@BotFather')}, send {mono('/newbot')}, pick a name and a username ending in {mono('bot')}. Copy the token it gives you.</>}>
        <a className={`link mono ${s.botLink}`} href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">open @BotFather in Telegram ↗</a>
      </StepRow>

      <StepRow n={2} title="Save the token" text="Stored encrypted and never shown again. Do not paste it anywhere else.">
        {asking ? (
          <form className={s.control} onSubmit={(e) => { e.preventDefault(); if (canSaveBot(botToken)) void saveBot(); }}>
            <div className={s.tokenRow}>
              <Field label="Bot token" type="password" className={s.tokenInput} autoComplete="off" value={botToken} onChange={(e) => { setBotToken(e.target.value); setSaveError(''); }} />
              <Button type="submit" disabled={!canSaveBot(botToken) || saving}>Save token</Button>
            </div>
            {saveError && <ErrorLine>{saveError}</ErrorLine>}
            {replacing && (
              <div className={`cap ${s.caption}`}>
                A new bot unlinks Telegram: you link the new one in the next row.{' '}
                <button type="button" className={s.quietLink} onClick={() => { setReplacing(false); setBotToken(''); setSaveError(''); }}>keep the current bot</button>
              </div>
            )}
          </form>
        ) : (
          <Live kind="ok" extra={<button type="button" className={s.quietLink} onClick={() => setReplacing(true)}>replace</button>}>
            saved and encrypted{link.botUsername ? ` · @${link.botUsername}` : ''}
          </Live>
        )}
      </StepRow>

      <StepRow n={3} title="Link your Telegram account" text="Open your bot and send this code. It works once and expires in 5 minutes. After that only you can use the bot.">
        {link.linked ? (
          <Live kind="ok">{linkedText(link)}</Live>
        ) : !link.botSaved || replacing ? (
          <Live kind="wait">save the bot token first</Live>
        ) : (
          <>
            {code ? (
              <div className={`${s.box} ${s.control}`}>
                <span className={`mono ${s.command}`}>{code.command}</span>
                <span className={s.timer}><span className={`mono ${s.small}`}>expires in {countdown(leftMs)}</span><CopyLink value={code.command} /></span>
              </div>
            ) : (
              <div className={s.control}>
                <Button disabled={pairBusy} onClick={() => void makeCode()}>{pairing || link.pairingPending ? 'Make a new code' : 'Make a code'}</Button>
                {pairing && <span className={`mono ${s.small}`} style={{ marginLeft: 12 }}>the last code expired</span>}
              </div>
            )}
            {pairError && <div className={s.err}><ErrorLine>{pairError}</ErrorLine></div>}
            <Live kind="wait">waiting for your message to the bot…</Live>
          </>
        )}
      </StepRow>

      <StepRow n={4} title="Sign in to the bot" text={<>Send {mono('/signin')}, then your 6-digit authenticator code. You stay signed in until {mono('/signout')}. Signed out, the bot sends nothing.</>}>
        {link.sessionActive
          ? <Live kind="ok">signed in · stays until you send /signout</Live>
          : <Live kind="wait">{signWaitText(link)}</Live>}
      </StepRow>
    </div>
  );
}
