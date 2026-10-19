'use client';

import { type FormEvent, useMemo, useState } from 'react';
import Link from 'next/link';
import type { z } from 'zod';
import type { AuthSessionRes } from '@/contracts';
import { checkPassword, passwordLabel, passwordScore } from '@/common';
import { AuthEm, AuthFrame } from '@/components/auth-frame';
import { Button, ErrorLine, Field } from '@/components/ui';
import { api, ApiError, errorText, fieldErrors } from '@/lib/api';

const RULES = [
  { key: 'len', label: 'At least 12 characters' },
  { key: 'common', label: 'Not a commonly used password' },
  { key: 'email', label: 'Does not contain your email name' },
] as const;

export default function CreateAccountPage() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [created, setCreated] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const checks = useMemo(() => checkPassword(password, email), [password, email]);
  const score = passwordScore(password, checks);
  const validEmail = /^\S+@\S+\.\S+$/.test(email);
  const matching = confirm.length > 0 && confirm === password;
  const canCreate = validEmail && checks.len && checks.common && checks.email && matching;

  async function createAccount(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canCreate) return;
    setBusy(true);
    setError('');
    try {
      await api.post<z.infer<typeof AuthSessionRes>>('/auth/register', {
        email,
        password,
        timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
      });
      setCreated(true);
    } catch (e) {
      if (e instanceof ApiError && e.code === 'forbidden') {
        window.location.assign('/sign-in');
        return;
      }
      setError(Object.values(fieldErrors(e))[0] ?? errorText(e, 'Could not create the account. Please try again.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthFrame
      right={<Link href="/sign-in" className="mono lbl signin-header-link">already have the account? sign in</Link>}
      glyph="create"
      title="Create your account"
      description="This app has one account: yours. Next you add a second step, then connect your phone."
      aside={
        <div className="signin-steps">
          <div className="lbl signin-steps-title">SETUP, IN ORDER</div>
          <div className="idx" aria-current="true"><span>Account</span><span className="v mono">now</span></div>
          <div className="idx signin-index-static"><span>Secure it</span><span className="v mono">next</span></div>
          <div className="idx signin-index-static"><span>Setup guide</span><span className="v mono">then</span></div>
        </div>
      }
    >
      {created ? (
        <div className="signin-form signin-success-state rise">
          <div className="signin-success" aria-hidden="true">✓</div>
          <div className="lbl">ACCOUNT CREATED</div>
          <p className="lead">Your account <AuthEm>{email}</AuthEm> exists. You cannot sign in properly until a second step is set up, so that comes next.</p>
          <Link href="/secure" className="btn lg">Secure your account</Link>
        </div>
      ) : (
        <form className="signin-form rise" onSubmit={createAccount}>
          <Field
            label="Email"
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => { setEmail(event.target.value); setError(''); }}
            required
          />
          <div className="field">
            <div className="signin-password-label">
              <label className="lbl" htmlFor="create-password">Password</label>
              <button className="signin-toggle" type="button" onClick={() => setShowPassword((shown) => !shown)}>
                {showPassword ? 'hide' : 'show'}
              </button>
            </div>
            <input
              id="create-password"
              className="uline"
              type={showPassword ? 'text' : 'password'}
              autoComplete="new-password"
              placeholder="at least 12 characters"
              value={password}
              onChange={(event) => { setPassword(event.target.value); setError(''); }}
              required
            />
            <div className="signin-strength">
              <div className="signin-strength-track" aria-label={`Password strength: ${passwordLabel(score) || 'empty'}`}>
                <div className="signin-strength-fill" data-score={score} style={{ width: `${score * 25}%` }} />
              </div>
              <span className="mono lbl">{passwordLabel(score)}</span>
            </div>
          </div>
          <Field
            label="Confirm password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="new-password"
            placeholder="type it once more"
            value={confirm}
            onChange={(event) => setConfirm(event.target.value)}
            required
          />
          <ul className="signin-rules">
            {RULES.map((rule) => (
              <li key={rule.key} data-met={checks[rule.key]}>
                <span aria-hidden="true" />
                {rule.label}
              </li>
            ))}
            <li data-met={matching}><span aria-hidden="true" />Both passwords match</li>
          </ul>
          {error && <ErrorLine>{error}</ErrorLine>}
          <div className="signin-actions">
            <Button large type="submit" disabled={!canCreate || busy}>{busy ? 'Creating…' : 'Create account'}</Button>
            <span className="mono lbl opt">stored as an Argon2id hash, never as text</span>
          </div>
        </form>
      )}
    </AuthFrame>
  );
}
