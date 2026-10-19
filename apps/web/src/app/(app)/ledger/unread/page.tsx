'use client';
import { useEffect, useState } from 'react';
import type { z } from 'zod';
import type { UnparsedRes } from '@/contracts';
import { AppShell } from '@/components/shell';
import { Empty, ErrorLine, LedgerMath, Loading, TextLink } from '@/components/ui';
import { errorText, useApi } from '@/lib/api';
import { useMe, useToday } from '@/lib/me';
import { type Done, tally, type UnreadItem } from '@/features/unread';
import { Message } from './message';
import s from './page.module.css';

type Queue = z.infer<typeof UnparsedRes>;

export default function UnreadPage() {
  const today = useToday();
  const { mutate: mutateMe } = useMe();
  // Read once: each message keeps what was typed into it, so a refetch must not swap the list underneath it.
  const queue = useApi<Queue>('/unparsed', { revalidateOnFocus: false });
  const [items, setItems] = useState<UnreadItem[] | null>(null);
  const [status, setStatus] = useState<Record<string, Done>>({});
  useEffect(() => { if (queue.data && items === null) setItems(queue.data.items); }, [queue.data, items]);

  const t = tally(items?.length ?? 0, Object.values(status));
  const allSorted = items !== null && t.left === 0;

  const aside = (
    <>
      <div className={s.math}>
        <LedgerMath
          rows={[{ k: 'waiting', v: items ? items.length : '—' }, { k: '− sorted today', v: t.sorted }]}
          total={{ k: '= still to look at', v: items ? t.left : '—' }}
        />
      </div>
      <div className={`opt2 cap ${s.note}`}>Kept encrypted for 30 days, then deleted. One-time codes are never kept.</div>
      <div className={s.back}><TextLink href="/ledger" mono>← back to the ledger</TextLink></div>
    </>
  );

  return (
    <AppShell home="ledger" glyph="look" title="Needs a look" description="Bank messages the app could not read. Classify or delete them." aside={aside}>
      <div className={`rise ${s.head}`}>
        <div className="lbl">Unread messages</div>
        <h2 className={`fig-lg ${s.title}`}>Messages we could not read</h2>
        <p className={`cap ${s.lead}`}>
          These bank messages reached the server, but the wording was new. Add one as a payment and it joins the ledger like any other; the next message in that style may then read on its own.
        </p>
      </div>
      <div className={s.list}>
        {queue.error && !items && (
          <div style={{ padding: '12px 0' }}>
            <ErrorLine>{errorText(queue.error, 'Could not load your messages. Nothing was changed.')}</ErrorLine>
            <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void queue.mutate()}>Try again</TextLink></div>
          </div>
        )}
        {!items && !queue.error && <Loading>loading…</Loading>}
        {items?.map((it) => (
          <Message
            key={it.id} item={it} tz={today?.tz}
            onStatus={(id, done) => setStatus((st) => ({ ...st, [id]: done }))} onSettled={() => void mutateMe()}
          />
        ))}
        {allSorted && <Empty>All sorted. Messages the app cannot read will wait here.</Empty>}
        <div className={`mono lbl ${s.foot}`}>Kept 30 days. Deleting here is permanent.</div>
      </div>
    </AppShell>
  );
}
