'use client';
import type { RecurringRuleDto } from '@/contracts';
import { AppShell } from '@/components/shell';
import { ErrorLine, Loading, SectionTabs, TextLink } from '@/components/ui';
import { api, errorText, useApi } from '@/lib/api';
import { plain } from '@/common';
import { useToday } from '@/lib/me';
import { committedRows, committedTotal, rangeText, type RecurringList, withoutRule, withRule } from '@/features/repeats';
import { NewRule } from './new-rule';
import { RulesTable } from './rules-table';
import { Timeline } from './timeline';
import s from './page.module.css';

interface RuleAnswer { rule: RecurringRuleDto }

export default function RepeatsPage() {
  const today = useToday();
  const { data, error, mutate } = useApi<RecurringList>('/recurring');
  const cats = useApi<{ items: { name: string; archived: boolean }[] }>('/categories');
  const tags = (cats.data?.items ?? []).filter((c) => !c.archived).map((c) => c.name);

  /** Put the server's answer into the list straight away (no second fetch). */
  const commit = (update: (cur: RecurringList) => RecurringList) => mutate((cur) => (cur ? update(cur) : cur), { revalidate: false });
  const saved = async (res: RuleAnswer) => { await commit((cur) => withRule(cur, res.rule)); void cats.mutate(); };

  async function onPause(rule: RecurringRuleDto, paused: boolean) {
    if (!data) return;
    await mutate(async (cur) => {
      const res = await api.patch<RuleAnswer>(`/recurring/${rule.id}`, { paused });
      return withRule(cur ?? data, res.rule);
    }, { optimisticData: withRule(data, { ...rule, paused }), rollbackOnError: true, revalidate: false });
  }

  const rules = data?.items ?? [];
  const rows = committedRows(rules);
  const aside = (
    <>
      <div className={`lbl ${s.block}`}>Committed each month</div>
      <div className="mono" style={{ fontSize: 'var(--fs-s)' }}>
        {rows.map((r) => (
          <div key={r.id} className={s.sumRow} data-off={r.off}>
            <span className={s.k}>{r.label}{r.off && <span className="sr"> (paused, not counted)</span>}</span><span>{plain(r.amountMinor)}</span>
          </div>
        ))}
        <div className={s.sumTotal}><span>= committed</span><span>{data && rules.length > 0 ? plain(committedTotal(rules)) : '—'}</span></div>
      </div>
      <div className={`opt2 cap ${s.note}`}>A payment logged within 2 days of its due date links to the rule, never counted twice.</div>
    </>
  );

  const status = error && !data
    ? <div style={{ textAlign: 'center' }}><ErrorLine>{errorText(error, 'Could not load your repeating payments.')}</ErrorLine><div style={{ marginTop: 8 }}><TextLink mono onClick={() => void mutate()}>Try again</TextLink></div></div>
    : !data || !today ? <Loading>loading…</Loading> : null;

  return (
    <AppShell home="money" glyph="money" title="Money" description="Payments that leave on their own post on the due date. Everything else is in Activity." aside={aside}>
      <div className={s.tabs}>
        <SectionTabs label="Money" tabs={[
          { href: '/money', label: 'Activity', active: false },
          { href: '/money/repeats', label: 'Repeats', count: data ? rules.length : undefined, active: true },
        ]} />
      </div>
      <div className={s.head}>
        <h2 className="h2">The next 30 days</h2>
        <div className="lbl" style={{ textTransform: 'none' }}>stem height = amount{today ? ` · ${rangeText(today.today)}` : ''}</div>
      </div>
      <Timeline rules={rules} today={today?.today ?? null} status={status} />
      <RulesTable
        rules={rules} tags={tags}
        onPause={onPause}
        onChange={async (id, body) => saved(await api.patch<RuleAnswer>(`/recurring/${id}`, body))}
        onSkip={async (id) => saved(await api.patch<RuleAnswer>(`/recurring/${id}`, { skipNext: true }))}
        onRemove={async (id) => { await api.del(`/recurring/${id}`); await commit((cur) => withoutRule(cur, id)); }}
      />
      {today && data && <NewRule today={today.today} tags={tags} onCreate={async (body) => saved(await api.post<RuleAnswer>('/recurring', body))} />}
    </AppShell>
  );
}
