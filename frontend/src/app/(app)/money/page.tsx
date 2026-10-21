'use client';
import { type UIEvent, useEffect, useState } from 'react';
import type { z } from 'zod';
import type { CategoriesUsageRes } from '@/contracts';
import { CheckPanel } from '@/components/check-panel';
import { AppShell } from '@/components/shell';
import { Empty, ErrorLine, IndexList, Loading, Segmented, SectionTabs, StripLink, TextLink } from '@/components/ui';
import { useApi } from '@/lib/api';
import { inr, shortMonth } from '@/common';
import { useMe, useToday } from '@/lib/me';
import { CAT_ALL, categoryIndex, endMark, isSrcFilter, isUnaccountedOpen, type TransactionRow, lookText, rowView, shownText, SOURCE_FILTERS, splitChoices, type SrcFilter } from '@/features/transactions';
import { nextDue } from '@/features/now';
import { nextRule, type RecurringList } from '@/features/repeats';
import { TransactionRowItem } from './transaction-row';
import { SplitPanel } from './split-panel';
import { TagWell } from './tag-well';
import { useTransactions } from './use-transactions';
import s from './page.module.css';

/** Within this many pixels of the bottom of the list the next page is fetched. */
const LOAD_AHEAD = 30;

export default function TransactionsPage() {
  const today = useToday();
  const month = today?.month ?? null;
  const { data: me, mutate: mutateMe } = useMe();
  const categories = useApi<z.infer<typeof CategoriesUsageRes>>('/categories?sort=usage');
  const recurring = useApi<RecurringList>('/recurring');
  const next = recurring.data ? nextRule(recurring.data.items) : null;

  const [cat, setCat] = useState(CAT_ALL);
  const [src, setSrc] = useState<SrcFilter>('all');
  // a link from Now (`/money?cat=needs-tag`, redirected from the old `/transactions` address) lands on its filter
  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    const wantedSrc = q.get('src');
    if (isSrcFilter(wantedSrc)) setSrc(wantedSrc);
    const wantedCat = q.get('cat');
    if (wantedCat) setCat(wantedCat);
  }, []);

  const { view, loading, loadingMore, error, loadMore, refresh, reload } = useTransactions(cat, src, month);
  const [checkOpen, setCheckOpen] = useState(false);
  // "Check now" on Devices lands here with the panel open
  useEffect(() => { if (new URLSearchParams(window.location.search).get('check') === '1') setCheckOpen(true); }, []);
  const [tagging, setTagging] = useState<string | null>(null);
  const [splitting, setSplitting] = useState<TransactionRow | null>(null);

  const changed = () => { void refresh(); void mutateMe(); void categories.mutate(); };
  const index = view ? categoryIndex(view.counts, cat) : [];
  const end = view ? endMark(view.rows.length, view.nextCursor) : 'none';

  const onScroll = (e: UIEvent<HTMLDivElement>) => {
    const el = e.currentTarget;
    if (!loading && !loadingMore && el.scrollTop + el.clientHeight >= el.scrollHeight - LOAD_AHEAD) void loadMore();
  };

  const aside = (
    <>
      <div className="lbl" style={{ marginTop: 24, paddingBottom: 7, borderBottom: '1px solid var(--ink)' }}>
        By category · {today ? shortMonth(today.month) : ''} total
      </div>
      <IndexList label="Category" items={index.map((i) => ({ ...i, active: i.key === cat, onClick: () => setCat(i.key) }))} />
      <div className="opt2" style={{ marginTop: 24, borderTop: '1px solid var(--rule)', paddingTop: 14 }}>
        <div className="lbl">Log it in Telegram</div>
        <div className="mono cap" style={{ marginTop: 6, lineHeight: 1.9 }}>/350 food<br />+1500 salary</div>
      </div>
    </>
  );

  return (
    <AppShell home="money" glyph="money" title="Money" description="Everything that left or came in, and what repeats next." aside={aside}>
      <SectionTabs
        label="Money" hint="Everything you logged, newest first."
        tabs={[
          { href: '/money', label: 'Activity', active: true },
          { href: '/money/repeats', label: 'Repeats', count: recurring.data?.items.length, active: false },
        ]}
      />
      <div className={`strip ${s.strip}`}>
        <StripLink tag="LOOK" href="/money/unread">{lookText(me?.needsLookCount ?? 0)}</StripLink>
        <button type="button" aria-expanded={checkOpen} onClick={() => setCheckOpen((v) => !v)}>
          <span className="lbl">CHECK</span><span>Compare with your bank’s balance</span><span aria-hidden="true">{checkOpen ? '↑' : '↓'}</span>
        </button>
        {next && <StripLink tag="NEXT" href="/money/repeats">{next.name} {inr(next.amountMinor)} on {nextDue(next.nextDue)}</StripLink>}
      </div>
      {checkOpen && view && <CheckPanel listBelow transactionsMinor={view.balanceMinor} onChanged={changed} />}
      {splitting && view && (
        <SplitPanel
          key={splitting.id} row={splitting} choices={splitChoices(view.counts)}
          onSplit={() => { setSplitting(null); changed(); }} onClose={() => setSplitting(null)}
        />
      )}

      <div className={s.top}>
        <div className={`mono ${s.count}`}>{view ? shownText(view.rows.length, view.matching, month) : ' '}</div>
        <Segmented<SrcFilter> label="Source" value={src} onChange={setSrc} options={SOURCE_FILTERS} />
      </div>

      <div className={s.tableWrap}>
        <div className={s.table}>
          <div className={`${s.thead} th-row lbl`}>
            <div className={s.cDate}>Date</div>
            <div className={s.cWhat}>What</div>
            <div className={s.cTag}>Tag</div>
            <div className={s.cSource}>Source</div>
            <div className={`${s.cAmount}`}>Amount</div>
          </div>
          <div className={`${s.panel} ${loading && view ? s.stale : ''}`} onScroll={onScroll}>
            {!view && error && (
              <div style={{ padding: '12px 0' }}>
                <ErrorLine>{error}</ErrorLine>
                <div style={{ marginTop: 8 }}><TextLink mono onClick={() => void reload()}>Try again</TextLink></div>
              </div>
            )}
            {!view && !error && <Loading>loading…</Loading>}
            {view && view.rows.map((r) => (
              <div key={r.id} className={s.rowWrap}>
                <TransactionRowItem
                  v={rowView(r, today?.tz)} tagging={tagging === r.id}
                  onTag={() => setTagging(tagging === r.id ? null : r.id)}
                  onSplit={() => { setCheckOpen(false); setSplitting(isUnaccountedOpen(r) ? r : null); }}
                />
                {tagging === r.id && (
                  <TagWell
                    row={r} categories={categories.data?.items ?? []}
                    onTagged={() => { setTagging(null); changed(); }} onClose={() => setTagging(null)}
                  />
                )}
              </div>
            ))}
            {view && view.rows.length === 0 && <Empty>{cat === CAT_ALL && src === 'all' ? 'Nothing yet. Payments you log in Telegram land here.' : 'Nothing matches this view.'}</Empty>}
            {view && error && <div style={{ padding: '12px 0' }}><ErrorLine>{error}</ErrorLine></div>}
            {end === 'more' && !loadingMore && <div className={s.tail}><TextLink mono onClick={() => void loadMore()}>load older entries ↓</TextLink></div>}
            {loadingMore && <div className={`mono pulse ${s.endNote}`} role="status">loading older entries…</div>}
            {end === 'end' && <div className={`mono ${s.endNote}`}>that’s everything for this view</div>}
          </div>
        </div>
      </div>
      <div className={`mono lbl ${s.foot}`} style={{ textTransform: 'none' }}>scroll the list to load older entries</div>
    </AppShell>
  );
}
