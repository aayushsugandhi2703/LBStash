'use client';
import { useEffect, useRef, useState } from 'react';
import type { z } from 'zod';
import type { ConfirmEmailRes } from '@/contracts';
import { AccountShell } from '@/components/shell';
import { ErrorLine, GhostLink } from '@/components/ui';
import { api, errorText } from '@/lib/api';
import { useMe } from '@/lib/me';
import { LineStatus } from '../parts';

type State = { kind: 'working' } | { kind: 'done'; email: string } | { kind: 'failed'; message: string };

/** Where the link in the "Confirm your new LBStash email" message lands: the token in the address is sent once. */
export default function ConfirmEmailPage() {
  const { mutate: mutateMe } = useMe();
  const [state, setState] = useState<State>({ kind: 'working' });
  const sent = useRef(false);

  useEffect(() => {
    if (sent.current) return; // a link works once: strict mode's second run must not use it up
    sent.current = true;
    const token = new URLSearchParams(window.location.search).get('token');
    if (!token) { setState({ kind: 'failed', message: 'Link incomplete. Open it again from the email, or request a new one on Profile.' }); return; }
    api.post<z.infer<typeof ConfirmEmailRes>>('/me/email/confirm', { token })
      .then((res) => { setState({ kind: 'done', email: res.user.email }); void mutateMe(); })
      .catch((e) => setState({ kind: 'failed', message: errorText(e, 'Could not confirm the new email. Nothing was changed.') }));
  }, [mutateMe]);

  return (
    <AccountShell
      page="profile" glyph="account" title="Account"
      description="Your profile and data. Sign-in is under Security."
      label="PROFILE" heading="Confirm your new email"
      lead="Open the link in the email to confirm your new sign-in address."
    >
      {state.kind === 'working' && <LineStatus kind="wait"><span className="mono">confirming…</span></LineStatus>}
      {state.kind === 'done' && (
        <>
          <LineStatus>Your sign-in email is now {state.email}.</LineStatus>
          <div style={{ marginTop: 16 }}><GhostLink href="/account">Back to your profile</GhostLink></div>
        </>
      )}
      {state.kind === 'failed' && (
        <>
          <ErrorLine>{state.message}</ErrorLine>
          <div style={{ marginTop: 16 }}><GhostLink href="/account">Back to your profile</GhostLink></div>
        </>
      )}
    </AccountShell>
  );
}
