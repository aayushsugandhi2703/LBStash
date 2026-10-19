'use client';
import { timeOfDay } from '@/common';
import { ErrorLine, Loading, Segmented, Switch } from '@/components/ui';
import { AFTER_OPTIONS, DIGEST_OPTIONS, IDLE_OPTIONS, type TgSettings } from '@/features/devices';
import { previewButtons, previewLine2 } from '@/features/setup';
import s from './page.module.css';

/** Step 3: the one privacy decision (Reveal), how long the bot session lasts, and a live preview of the Telegram message. */
export function StepPrivacy({ settings, failed, error, save, retry }: {
  settings: TgSettings | undefined; failed: boolean; error: string; save: (patch: Partial<TgSettings>) => void; retry: () => void;
}) {
  if (!settings) {
    return failed
      ? <div className={s.done}><ErrorLine>Could not read your Telegram settings.</ErrorLine><button type="button" className={`link mono ${s.caption}`} onClick={retry}>Try again</button></div>
      : <Loading />;
  }
  return (
    <div className={`rise ${s.privacy}`}>
      <div className={s.left}>
        <div className={`lbl ${s.under}`}>WHAT TELEGRAM NEVER GETS</div>
        <div className={s.never}>No amount, no payee, no balance, no account number, no bank name, no UPI ID, no original message. Each message only says that money went out or came in, and when.</div>
        <div className="settings-row">
          <div style={{ minWidth: 0 }}>
            <div className="t">Show a Reveal button</div>
            <div className="s">Tap it to see the amount and payee for 30 seconds. While visible, those details pass through Telegram. Off means Telegram never sees any bank detail.</div>
          </div>
          <Switch checked={settings.allowReveal} label="Show a Reveal button" onChange={(v) => save({ allowReveal: v })} />
        </div>

        <div className={s.segBlock}>
          <div className="lbl">ALSO SIGN ME OUT OF THE BOT AFTER</div>
          <Segmented label="Idle days" value={String(settings.sessionIdleDays)} options={IDLE_OPTIONS.map((o) => ({ value: String(o.value), label: o.label }))} onChange={(v) => save({ sessionIdleDays: Number(v) })} />
          <div className={`cap ${s.segNote}`}>You stay signed in until you send /signout. This is only a safety net for when you stop using the bot.</div>
        </div>
        <div className={s.segBlock}>
          <div className="lbl">DAILY REMINDER OF UNTAGGED PAYMENTS</div>
          <Segmented label="Digest" value={settings.digestMode} options={DIGEST_OPTIONS} onChange={(v) => save({ digestMode: v })} />
        </div>
        <div className={s.segBlock}>
          <div className="lbl">AFTER YOU TAG A PAYMENT</div>
          <Segmented label="After tagging" value={settings.afterTag} options={AFTER_OPTIONS} onChange={(v) => save({ afterTag: v })} />
        </div>
        {error && <ErrorLine>{error}</ErrorLine>}
      </div>

      <div className={s.right}>
        <div className={`lbl ${s.under}`}>HOW IT WILL LOOK IN TELEGRAM</div>
        <div className={s.preview}>
          <div className={`mono ${s.l1}`}>Money out · {timeOfDay(new Date())}</div>
          <div className={`mono ${s.l2}`}>{previewLine2(settings.allowReveal)}</div>
          <div className={`mono ${s.buttons}`}>{previewButtons(settings.allowReveal).map((b) => <span key={b}>{b}</span>)}</div>
        </div>
        <div className={`mono ${s.small} ${s.previewNote}`}>Your own category names do show on the buttons. Nothing about the bank does.</div>
      </div>
    </div>
  );
}
