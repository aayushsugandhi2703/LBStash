'use client';

import { type FormEvent, useState } from 'react';
import Link from 'next/link';
import { checkPassword } from '@/common';
import { AuthEm, AuthFrame } from '@/components/auth-frame';
import { Button, ErrorLine, Field } from '@/components/ui';
import { api, ApiError, errorText, fieldErrors } from '@/lib/api';

const INVALID = "That email or recovery code isn't valid.";

type Step = 'code' | 'password' | 'done';

export default function ResetPage() {
  const [step, setStep] = useState<Step>('code');
  const [email, setEmail] = useState('');
  const [recoveryCode, setRecoveryCode] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const checks = checkPassword(password, email);
  const validPassword = checks.len && checks.common && checks.email && confirm.length > 0 && password === confirm;

  async function verifyCode(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (!/^\S+@\S+\.\S+$/.test(email) || recoveryCode.length < 9) {
      setError(INVALID);
      return;
    }
    setBusy(true);
    try {
      const result = await api.post<{ resetToken: string }>('/auth/reset/verify', { email, recoveryCode });
      setResetToken(result.resetToken);
      setStep('password');
    } catch (e) {
      setError(errorText(e, INVALID));
    } finally {
      setBusy(false);
    }
  }

  async function savePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!validPassword) return;
    setError('');
    setBusy(true);
    try {
      await api.post('/auth/reset/complete', { resetToken, newPassword: password });
      setStep('done');
    } catch (e) {
      setError(fieldErrors(e).newPassword ?? errorText(e, 'Could not reset the password. Start again with your recovery code.'));
      // the reset window (or the code) is gone: only a fresh check can go on
      if (e instanceof ApiError && e.code === 'unprocessable') setStep('code');
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame
      right={<Link href="/sign-in" className="mono lbl signin-header-link">back to sign in</Link>}
      glyph="reset"
      title="Reset your password"
      description={'There is no "email me a link" here, on purpose. A recovery code proves it is you, and nobody else can intercept it.'}
      aside={
        <div className="math mono signin-math">
          <div className="r"><span className="k">you need</span><span>1 recovery code</span></div>
          <div className="r"><span className="k">other sessions</span><span>signed out</span></div>
          <div className="r total"><span className="k">= code used up</span><span className="v">once</span></div>
        </div>
      }
    >
      {step === 'code' && (
        <form className="signin-form rise" onSubmit={verifyCode} noValidate>
          <div className="lbl">STEP 1 OF 2 · PROVE IT IS YOU</div>
          <Field
            label="Email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => { setEmail(event.target.value); setError(''); }}
            required
          />
          <Field
            label="One of your recovery codes"
            type="text"
            className="mono"
            autoComplete="off"
            placeholder="xxxx-xxxx"
            value={recoveryCode}
            onChange={(event) => { setRecoveryCode(event.target.value); setError(''); }}
            required
          />
          {error && <ErrorLine>{error}</ErrorLine>}
          <div className="signin-actions">
            <Button large type="submit" disabled={busy}>{busy ? 'Checking…' : 'Continue'}</Button>
            <span className="mono lbl opt">lost the codes too? you will need to restore from a backup</span>
          </div>
        </form>
      )}

      {step === 'password' && (
        <form className="signin-form rise" onSubmit={savePassword}>
          <div className="lbl">STEP 2 OF 2 · NEW PASSWORD</div>
          <div className="field">
            <div className="signin-password-label">
              <label className="lbl" htmlFor="reset-password">New password</label>
              <button className="signin-toggle" type="button" onClick={() => setShowPassword((shown) => !shown)}>
                {showPassword ? 'hide' : 'show'}
              </button>
            </div>
            <input
              id="reset-password"
              className="uline"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="at least 12 characters"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <Field
            label="Confirm"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            placeholder="type it once more"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            required
          />
          <ul className="signin-rules">
            <li data-met={checks.len}><span aria-hidden="true" />At least 12 characters</li>
            <li data-met={checks.common}><span aria-hidden="true" />Not a commonly used password</li>
            <li data-met={checks.email}><span aria-hidden="true" />Does not contain your email name</li>
            <li data-met={confirm.length > 0 && confirm === password}><span aria-hidden="true" />Both passwords match</li>
          </ul>
          {error && <ErrorLine>{error}</ErrorLine>}
          <div className="signin-actions">
            <Button large type="submit" disabled={!validPassword || busy}>{busy ? 'Saving…' : 'Set new password'}</Button>
            <button type="button" className="signin-back" onClick={() => { setStep('code'); setError(''); }}>Back</button>
          </div>
        </form>
      )}

      {step === 'done' && (
        <div className="signin-form signin-success-state rise">
          <div className="signin-success" aria-hidden="true">✓</div>
          <div className="lbl">PASSWORD CHANGED</div>
          <p className="lead">All other sessions were signed out. The recovery code you used is <AuthEm>used up</AuthEm>, so sign in and make a fresh set of codes.</p>
          <div className="signin-actions">
            <Link href="/sign-in" className="btn lg">Sign in</Link>
            <Link href="/sign-in?next=%2Fsecure%3Frefresh%3D1" className="signin-back signin-link">Get new recovery codes</Link>
          </div>
        </div>
      )}
    </AuthFrame>
  );
}
