'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { LedgerPageDto } from '@/contracts';
import { api, errorText } from '@/lib/api';
import { type LedgerCounts, ledgerQuery, type LedgerRow, mergePage, PAGE_FIRST, PAGE_NEXT, refreshSize, type SrcFilter } from '@/features/ledger';

interface LedgerView {
  rows: LedgerRow[];
  nextCursor: string | null;
  matching: number;
  counts: LedgerCounts;
  balanceMinor: number;
}

const viewOf = (p: LedgerPageDto, rows: LedgerRow[] = p.items): LedgerView => ({
  rows, nextCursor: p.nextCursor, matching: p.matching, counts: p.counts, balanceMinor: p.balanceMinor,
});

/** The Ledger list for one filter: a first page, "load older entries" appended below it, and `refresh` after a write (one request for as many rows as are on screen). */
export function useLedger(cat: string, src: SrcFilter, month: string | null) {
  const [view, setView] = useState<LedgerView | null>(null);
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
      const p = await api.get<LedgerPageDto>(`/ledger?${ledgerQuery({ cat, src, month, limit })}`);
      if (id === latest.current) setView(viewOf(p));
    } catch (e) {
      if (id === latest.current) setError(errorText(e, 'Could not load the ledger. Try again.'));
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
      const p = await api.get<LedgerPageDto>(`/ledger?${ledgerQuery({ cat, src, month, cursor, limit: PAGE_NEXT })}`);
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
