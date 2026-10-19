'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import type { z } from 'zod';
import type { AuditRes, LedgerPageDto } from '@/contracts';
import { AccountShell } from '@/components/shell';
import { Button, CodeInput, ErrorLine, GhostButton, LedgerMath, Loading, SettingsRow, TextLink } from '@/components/ui';
import { api, errorText, fieldErrors, useApi } from '@/lib/api';
import { useMe } from '@/lib/me';
import { buildExportFile, canDelete, codeError, exportLine, type ExportResult, isCode, isEmail, nameDirty, profileSummary, shortDate } from '@/features/account';
import { downloadText } from '@/lib/browser';
import { LineStatus, LoadError, Section, Well } from './parts';
import s from './account.module.css';

type Ask = '' | 'export' | 'delete';
type ExportState = { kind: 'idle' } | { kind: 'working' } | { kind: 'ready'; filename: string; text: string; line: string };

const AUDIT_LIMIT = 200;

export default function ProfilePage() {
  const router = useRouter();
  const { data: me, error: meError, mutate: mutateMe, isLoading } = useMe();
  const audit = useApi<z.infer<typeof AuditRes>>(`/audit?limit=${AUDIT_LIMIT}`);
  const ledger = useApi<z.infer<typeof LedgerPageDto>>('/ledger?limit=1');

  const [name, setName] = useState('');
  const [savedName, setSavedName] = useState('');
  const [nameSaved, setNameSaved] = useState(false);
  const [nameError, setNameError] = useState('');
  const [nameBusy, setNameBusy] = useState(false);
  useEffect(() => { if (me) { setName(me.name ?? ''); setSavedName(me.name ?? ''); } }, [me?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  const [emailEdit, setEmailEdit] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [emailCode, setEmailCode] = useState('');
  const [emailSent, setEmailSent] = useState('');
  const [emailError, setEmailError] = useState('');
  const [emailCodeError, setEmailCodeError] = useState('');
  const [emailBusy, setEmailBusy] = useState(false);

  // export and delete share one code field; only one well is open at a time
  const [ask, setAsk] = useState<Ask>('');
  const [askCode, setAskCode] = useState('');
  const [delText, setDelText] = useState('');
  const [askError, setAskError] = useState('');
  const [busy, setBusy] = useState(false);
  const [exp, setExp] = useState<ExportState>({ kind: 'idle' });
  const [signingOut, setSigningOut] = useState(false);

  async function saveName() {
    setNameBusy(true); setNameError('');
    try {
      await api.patch('/me', { name: name.trim() });
      setSavedName(name.trim()); setName(name.trim()); setNameSaved(true);
      await mutateMe();
    } catch (e) {
      setNameError(fieldErrors(e).name ?? errorText(e));
    } finally { setNameBusy(false); }
  }

  function toggleEmail() {
    setEmailEdit((v) => !v); setEmailSent(''); setNewEmail(''); setEmailCode(''); setEmailError(''); setEmailCodeError('');
  }
  async function sendEmail() {
    setEmailBusy(true); setEmailError(''); setEmailCodeError('');
    try {
      const r = await api.post<{ pendingEmail: string }>('/me/email', { newEmail: newEmail.trim(), code: emailCode });
      setEmailEdit(false); setEmailSent(r.pendingEmail); setNewEmail(''); setEmailCode('');
      await mutateMe();
    } catch (e) {
      const fe = fieldErrors(e);
      if (fe.newEmail) setEmailError(fe.newEmail);
      else setEmailCodeError(codeError(e) ?? errorText(e));
      setEmailCode('');
    } finally { setEmailBusy(false); }
  }

  function toggleAsk(which: Exclude<Ask, ''>) {
    setAsk(ask === which ? '' : which); setAskCode(''); setDelText(''); setAskError('');
    if (which === 'export') setExp({ kind: 'idle' });
  }
  async function runExport() {
    setBusy(true); setAskError('');
    try {
      setExp({ kind: 'working' }); setAsk('');
      const res = await api.post<ExportResult>('/account/export', { code: askCode });
      const f = buildExportFile(res);
      setExp({ kind: 'ready', filename: f.filename, text: f.text, line: exportLine(f) });
      setAskCode('');
      void audit.mutate();
    } catch (e) {
      setExp({ kind: 'idle' }); setAsk('export'); setAskCode('');
      setAskError(codeError(e) ?? errorText(e));
    } finally { setBusy(false); }
  }
  async function runDelete() {
    setBusy(true); setAskError('');
    try {
      await api.del('/account', { confirm: 'DELETE', code: askCode });
      setAsk(''); setAskCode(''); setDelText('');
      await mutateMe();
    } catch (e) {
      setAskCode('');
      setAskError(codeError(e) ?? errorText(e));
    } finally { setBusy(false); }
  }
  async function cancelDeletion() {
    setBusy(true); setAskError('');
    try { await api.post('/account/restore'); await mutateMe(); } catch (e) { setAskError(errorText(e)); } finally { setBusy(false); }
  }
  async function signOut() {
    setSigningOut(true);
    try { await api.post('/auth/logout'); } catch { /* the cookie is gone once the server answers; go on either way */ }
    router.replace('/sign-in');
  }

  const sum = profileSummary(audit.data?.entries ?? [], AUDIT_LIMIT);
  const kept = ledger.data ? String(ledger.data.counts.all) : '—';
  const dirty = nameDirty(name, savedName);
  const pending = emailSent || me?.pendingEmail || '';

  return (
    <AccountShell
      page="profile" glyph="account" title="Account"
      description="Your profile and data. Sign-in is under Security."
      label="PROFILE" heading="Your account"
      lead="Sensitive changes ask for your authenticator code."
      summary={<LedgerMath rows={[{ k: 'member since', v: audit.data ? sum.memberSince : '—' }, { k: 'entries kept', v: kept }, { k: 'last export', v: audit.data ? sum.lastExport : '—' }]} total={{ k: '= your data', v: 'yours' }} />}
    >
      {isLoading && !me && <Loading />}
      {meError && !me && <LoadError retry={() => void mutateMe()} />}
      {me && (
        <>
          <Section first>PROFILE</Section>
          <div className={s.labelRow}>
            <label htmlFor="name" className="lbl">NAME</label>
            <input id="name" className={`${s.input} ${s.grow}`} type="text" autoComplete="name" placeholder="Your name" value={name} maxLength={80} onChange={(e) => { setName(e.target.value); setNameSaved(false); setNameError(''); }} />
          </div>
          {dirty && (
            <div className={`rise ${s.actionsRow}`}>
              <Button onClick={() => void saveName()} disabled={nameBusy}>Save name</Button>
              <TextLink mono onClick={() => setName(savedName)}>Undo</TextLink>
              <span className="mono lbl" style={{ textTransform: 'none' }}>unsaved change</span>
            </div>
          )}
          {nameError && <ErrorLine>{nameError}</ErrorLine>}
          {nameSaved && !dirty && <LineStatus>Name saved.</LineStatus>}

          <div className={s.labelRow}>
            <span className="lbl">EMAIL</span>
            <span className={`${s.grow} ${s.ellipsis}`}>{me.email}</span>
            <TextLink mono onClick={toggleEmail}>{emailEdit ? 'Cancel' : 'Change email'}</TextLink>
          </div>
          {emailEdit && (
            <Well>
              <label htmlFor="newemail" className="lbl">NEW EMAIL</label>
              <input id="newemail" className={`${s.input} ${emailError ? s.err : ''}`} type="email" autoComplete="off" placeholder="new@example.com" value={newEmail} onChange={(e) => { setNewEmail(e.target.value); setEmailError(''); }} />
              {emailError && <ErrorLine>{emailError}</ErrorLine>}
              <div className={`actions ${s.field}`}>
                <CodeInput value={emailCode} onChange={(v) => { setEmailCode(v); setEmailCodeError(''); }} />
                <Button disabled={!(isEmail(newEmail) && isCode(emailCode)) || emailBusy} onClick={() => void sendEmail()}>Send confirmation link</Button>
                {emailCodeError && <div className={s.full}><ErrorLine>{emailCodeError}</ErrorLine></div>}
              </div>
              <div className={s.note}>We email a link to the new address. Open it to confirm.</div>
            </Well>
          )}
          {pending && !emailEdit && <LineStatus>Link sent to {pending}. Nothing changes until you open it.</LineStatus>}

          <Section>REGION</Section>
          <SettingsRow title="Rupees, India time" sub="Money is in ₹ with Indian grouping; days end at midnight India time. Fixed for now.">
            <span className={`mono ${s.mono13}`}>₹ · IST</span>
          </SettingsRow>

          <Section>YOUR DATA</Section>
          <SettingsRow title="Export everything" sub="Every entry, tag, plan, limit and repeat in one file, saved to your device.">
            <GhostButton onClick={() => toggleAsk('export')} disabled={exp.kind === 'working'}>{ask === 'export' ? 'Cancel' : 'Export'}</GhostButton>
          </SettingsRow>
          {ask === 'export' && (
            <Well>
              <div className="actions">
                <CodeInput value={askCode} onChange={(v) => { setAskCode(v); setAskError(''); }} />
                <Button disabled={!isCode(askCode) || busy} onClick={() => void runExport()}>Make the file</Button>
                {askError && <div className={s.full}><ErrorLine>{askError}</ErrorLine></div>}
              </div>
            </Well>
          )}
          {exp.kind === 'working' && <LineStatus kind="wait"><span className="mono">packing your entries…</span></LineStatus>}
          {exp.kind === 'ready' && (
            <div className={`rise ${s.lineRow}`} role="status">
              <span className={s.lead}><span aria-hidden="true" className={s.sq} /><span className="mono" style={{ fontSize: 'var(--fs-s)' }}>{exp.line}</span></span>
              <Button onClick={() => downloadText(exp.filename, exp.text)}>Download</Button>
            </div>
          )}

          <SettingsRow title="Delete account" sub="Deletes your ledger, tokens, passkeys and Telegram link after 7 days. Sign in before then to cancel. After that it is final.">
            <GhostButton bad onClick={() => toggleAsk('delete')} disabled={Boolean(me.deleteAfter)}>{ask === 'delete' ? 'Cancel' : 'Delete account'}</GhostButton>
          </SettingsRow>
          {ask === 'delete' && !me.deleteAfter && (
            <Well>
              <label htmlFor="dtext" className="lbl">TYPE DELETE TO CONFIRM</label>
              <input id="dtext" className={s.input} type="text" autoComplete="off" placeholder="DELETE" value={delText} onChange={(e) => setDelText(e.target.value)} />
              <div className={`actions ${s.field}`}>
                <CodeInput value={askCode} onChange={(v) => { setAskCode(v); setAskError(''); }} />
                <GhostButton bad disabled={!canDelete(delText, askCode) || busy} onClick={() => void runDelete()}>Schedule deletion</GhostButton>
                {askError && <div className={s.full}><ErrorLine>{askError}</ErrorLine></div>}
              </div>
            </Well>
          )}
          {me.deleteAfter && (
            <div role="status" className={`rise ${s.lineRow}`}>
              <span className={s.lead}><span aria-hidden="true" className={`${s.sq} ${s.stop}`} /><span className={s.red} style={{ fontSize: 'var(--fs-s)' }}>Deletion is scheduled for {shortDate(me.deleteAfter)}. Signing in before then cancels it.</span></span>
              <TextLink mono onClick={() => void cancelDeletion()}>Cancel deletion</TextLink>
            </div>
          )}
          {askError && ask === '' && <ErrorLine>{askError}</ErrorLine>}

          <Section>THIS BROWSER</Section>
          <SettingsRow title="Sign out" sub="Ends this browser's session. Other browsers and the bot stay signed in.">
            <GhostButton onClick={() => void signOut()} disabled={signingOut}>Sign out</GhostButton>
          </SettingsRow>
        </>
      )}
    </AccountShell>
  );
}
