'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { TransactionPageDto } from '@/contracts';
import { api, errorText } from '@/lib/api';
import { type TransactionCounts, transactionsQuery, type TransactionRow, mergePage, PAGE_FIRST, PAGE_NEXT, refreshSize, type SrcFilter } from '@/features/transactions';

interface TransactionsView {
  rows: TransactionRow[];
  nextCursor: string | null;
  matching: number;
  counts: TransactionCounts;
  balanceMinor: number;
}

const viewOf = (p: TransactionPageDto, rows: TransactionRow[] = p.items): TransactionsView => ({
  rows, nextCursor: p.nextCursor, matching: p.matching, counts: p.counts, balanceMinor: p.balanceMinor,
});

/** Transactions list for one filter: first page, older entries appended, `refresh` after a write. */
export function useTransactions(cat: string, src: SrcFilter, month: string | null) {
  const [view, setView] = useState<TransactionsView | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);
  const shown = useRef(0);
  shown.current = view?.rows.length ?? 0;

  const load = useCallback(async (limit: number, quiet: boolean) => {
    const id = ++latest.current;
    if (!quiet) setLoading(true);
    setError(null);
    try {
      const p = await api.get<TransactionPageDto>(`/transactions?${transactionsQuery({ cat, src, month, limit })}`);
      if (id === latest.current) setView(viewOf(p));
    } catch (e) {
      if (id === latest.current) setError(errorText(e, 'Could not load the transactions. Try again.'));
    } finally {
      if (id === latest.current) { setLoading(false); setLoadingMore(false); }
    }
  }, [cat, src, month]);

  useEffect(() => { if (month) void load(PAGE_FIRST, false); }, [load, month]);

  const loadMore = useCallback(async () => {
    const cursor = view?.nextCursor;
    if (!cursor || loadingMore) return;
    const id = latest.current;
    setLoadingMore(true);
    try {
      const p = await api.get<TransactionPageDto>(`/transactions?${transactionsQuery({ cat, src, month, cursor, limit: PAGE_NEXT })}`);
      if (id === latest.current) setView((v) => (v ? viewOf(p, mergePage(v.rows, p.items)) : v));
    } catch (e) {
      if (id === latest.current) setError(errorText(e, 'Could not load older entries. Try again.'));
    } finally {
      if (id === latest.current) setLoadingMore(false);
    }
  }, [view?.nextCursor, loadingMore, cat, src, month]);

  const refresh = useCallback(() => load(refreshSize(shown.current), true), [load]);
  const reload = useCallback(() => load(PAGE_FIRST, false), [load]);

  return { view, loading, loadingMore, error, loadMore, refresh, reload };
}
