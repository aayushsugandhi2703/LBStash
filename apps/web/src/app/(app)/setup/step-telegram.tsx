'use client';
import { useEffect, useState } from 'react';
import type { PairingRes } from '@/contracts';
import { Button, ErrorLine, Field } from '@/components/ui';
import { api, errorText, fieldErrors } from '@/lib/api';
import { countdown, type LinkStatus } from '@/features/devices';
import { canSaveBot, canSaveOwner, linkedText, signWaitText } from '@/features/setup';
import { CopyLink, Live, StepRow } from './parts';
import s from './page.module.css';

const mono = (t: string) => <span className="mono">{t}</span>;

/** Step 1: bot, token, owner, link code, sign-in. Reads `GET /telegram/link`, polled by the page. */
export function StepTelegram({ link, refresh }: { link: LinkStatus; refresh: () => void }) {
  const [botToken, setBotToken] = useState('');
  const [replacing, setReplacing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');
  const [owner, setOwner] = useState('');
  const [ownerBusy, setOwnerBusy] = useState(false);
  const [ownerError, setOwnerError] = useState('');
  const [pairing, setPairing] = useState<PairingRes | null>(null);
  const [pairBusy, setPairBusy] = useState(false);
  const [pairError, setPairError] = useState('');
  const [now, setNow] = useState(() => Date.now());

  // tick the code countdown
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
  async function saveOwner() {
    setOwnerBusy(true); setOwnerError('');
    try {
      await api.put('/telegram/owner', { telegram: owner.trim() });
      setOwner('');
      refresh();
    } catch (e) { setOwnerError(Object.values(fieldErrors(e))[0] ?? errorText(e)); } finally { setOwnerBusy(false); }
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
      <StepRow n={1} title="Create your bot" text={<>In Telegram, open {mono('@BotFather')}, send {mono('/newbot')}, copy the token.</>}>
        <a className={`link mono ${s.botLink}`} href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer">open @BotFather ↗</a>
      </StepRow>

      <StepRow n={2} title="Paste the token" text="Stored encrypted. Never shown again.">
        {asking ? (
          <form className={s.control} onSubmit={(e) => { e.preventDefault(); if (canSaveBot(botToken)) void saveBot(); }}>
            <div className={s.tokenRow}>
              <Field label="Bot token" type="password" className={s.tokenInput} autoComplete="off" placeholder="123456:ABC-DEF…" value={botToken} onChange={(e) => { setBotToken(e.target.value); setSaveError(''); }} />
              <Button type="submit" disabled={!canSaveBot(botToken) || saving}>Save token</Button>
            </div>
            {saveError && <ErrorLine>{saveError}</ErrorLine>}
            {replacing && (
              <div className={`cap ${s.caption}`}>
                A new bot unlinks Telegram. Link it again below.{' '}
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

      <StepRow n={3} title="Link your account" text="Add your username, then send the code to your bot. One use, 5 minutes.">
        {link.linked ? (
          <Live kind="ok">{linkedText(link)}</Live>
        ) : !link.botSaved || replacing ? (
          <Live kind="wait">paste the token first</Live>
        ) : (
          <>
            <form className={s.control} onSubmit={(e) => { e.preventDefault(); if (canSaveOwner(owner)) void saveOwner(); }}>
              <div className={s.tokenRow}>
                <Field label="Your Telegram username" type="text" className={s.tokenInput} autoComplete="off" placeholder={link.ownerTelegram ?? '@yourname'} value={owner} onChange={(e) => { setOwner(e.target.value); setOwnerError(''); }} />
                <Button type="submit" disabled={!canSaveOwner(owner) || ownerBusy}>{link.ownerTelegram ? 'Change' : 'Save'}</Button>
              </div>
              {ownerError && <ErrorLine>{ownerError}</ErrorLine>}
              <div className={`cap ${s.caption}`}>
                {link.ownerTelegram
                  ? <>Only {mono(link.ownerTelegram)} can link. Others are ignored.</>
                  : <>Your Telegram @username or numeric id.</>}
              </div>
            </form>
            {code ? (
              <div className={`${s.box} ${s.control}`}>
                <span className={`mono ${s.command}`}>{code.command}</span>
                <span className={s.timer}><span className={`mono ${s.small}`}>expires in {countdown(leftMs)}</span><CopyLink value={code.command} /></span>
              </div>
            ) : (
              <div className={s.control}>
                <Button disabled={pairBusy || !link.ownerTelegram} onClick={() => void makeCode()}>{pairing || link.pairingPending ? 'Make a new code' : 'Make a code'}</Button>
                {pairing && <span className={`mono ${s.small}`} style={{ marginLeft: 12 }}>the last code expired</span>}
              </div>
            )}
            {link.botUsername && (
              // with a live code the deep link opens your bot and sends `/start <code>` for you
              <a
                className={`link mono ${s.botLink}`}
                href={code ? `https://t.me/${link.botUsername}?start=${code.code}` : `https://t.me/${link.botUsername}`}
                target="_blank" rel="noopener noreferrer"
              >
                {code ? `open @${link.botUsername} and send the code ↗` : `open @${link.botUsername} in Telegram ↗`}
              </a>
            )}
            {pairError && <div className={s.err}><ErrorLine>{pairError}</ErrorLine></div>}
            <Live kind="wait">waiting for your message to the bot…</Live>
          </>
        )}
      </StepRow>

      <StepRow n={4} title="Sign in" text={<>Send {mono('/signin')}, then your 6-digit code.</>}>
        {link.sessionActive
          ? <Live kind="ok">signed in · until /signout</Live>
          : <Live kind="wait">{signWaitText(link)}</Live>}
      </StepRow>

      <StepRow
        n={5} title="Log a payment"
        text={<>{mono('/350 food')} is money out, {mono('+1500 salary')} is money in. Leave the tag off to pick one.</>}
      />
    </div>
  );
}
