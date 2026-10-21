'use client';
import { useState } from 'react';
import type { CreateRecurringReq } from '@/contracts';
import { Button } from '@/components/ui';
import { createBody, emptyForm } from '@/features/repeats';
import { RuleEditor } from './rule-editor';
import s from './page.module.css';

/** `+ New repeating payment`: the button opens the form under it and turns into Cancel while it is open. */
export function NewRule({ today, tags, onCreate }: { today: string; tags: string[]; onCreate: (body: CreateRecurringReq) => Promise<unknown> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className={s.newWrap}>
      <Button aria-expanded={open} onClick={() => setOpen((v) => !v)}>{open ? 'Cancel' : '+ New repeating payment'}</Button>
      {open && (
        <div style={{ marginTop: 12 }}>
          <RuleEditor
            initial={emptyForm(today)} build={(f) => createBody(f, today)} tags={tags} startsOn={{ min: today }} submitLabel="Add payment"
            submit={async (body) => { await onCreate(body); setOpen(false); }} onCancel={() => setOpen(false)}
          />
        </div>
      )}
    </div>
  );
}
