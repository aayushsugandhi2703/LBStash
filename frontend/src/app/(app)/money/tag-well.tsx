'use client';
import { useState } from 'react';
import { Button, Chip, ErrorLine, Field, TextLink } from '@/components/ui';
import { api, errorText } from '@/lib/api';
import { type TransactionRow, parseTagDraft, tagBody, type TagChoice, tagSuggestions, type UsageCategory } from '@/features/transactions';
import s from './page.module.css';

/** "tag it" under a row: one tap on a usual tag, or type a new one. Never a pop-up; it opens in the row's place. */
export function TagWell({ row, categories, onTagged, onClose }: {
  row: TransactionRow; categories: readonly UsageCategory[]; onTagged: () => void; onClose: () => void;
}) {
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const parsed = parseTagDraft(draft);
  const chips = tagSuggestions(draft, categories);

  async function submit(choice: TagChoice) {
    setBusy(true); setError('');
    try {
      await api.patch(`/transactions/${row.id}`, tagBody(choice));
      onTagged();
    } catch (e) {
      setError(errorText(e));
      setBusy(false);
    }
  }

  return (
    <form className={`well ${s.well}`} onSubmit={(e) => { e.preventDefault(); if (parsed.ok) void submit({ name: parsed.tag }); }}>
      <div className={s.tagRow}>
        <div className={s.tagField}>
          <Field label="Tag this entry" placeholder="#tag" autoComplete="off" autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} />
        </div>
        <Button type="submit" disabled={!parsed.ok || busy}>Tag it</Button>
        <TextLink mono onClick={onClose}>Cancel</TextLink>
      </div>
      {!parsed.ok && parsed.error && <ErrorLine>{parsed.error}</ErrorLine>}
      {error && <ErrorLine>{error}</ErrorLine>}
      {chips.length > 0 && (
        <div className={s.chips} role="group" aria-label="Usual tags">
          {chips.map((c) => <Chip key={c.name} onClick={() => !busy && void submit(c)}>#{c.name}</Chip>)}
        </div>
      )}
    </form>
  );
}
