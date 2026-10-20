'use client';
import { type ChangeEvent, useLayoutEffect, useRef, useState } from 'react';
import { type AmountOpts, groupIndian, reformat, toPaise } from '@/common';

/** Controlled rupee input: Indian grouping while typing, caret kept beside its digit. `value` is canonical ("12500"). */
export function useAmountField(initial = '', o: AmountOpts = {}) {
  const [value, setValue] = useState(initial);
  const ref = useRef<HTMLInputElement>(null);
  const caret = useRef<number | null>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (caret.current !== null && el && document.activeElement === el) el.setSelectionRange(caret.current, caret.current);
    caret.current = null;
  });

  const onChange = (e: ChangeEvent<HTMLInputElement>) => {
    const r = reformat(e.target.value, e.target.selectionStart ?? e.target.value.length, o);
    caret.current = r.caret;
    setValue(r.value);
  };

  return {
    value,
    setValue,
    paise: toPaise(value),
    inputProps: { ref, value: groupIndian(value), onChange, inputMode: (o.decimals ? 'decimal' : 'numeric') as 'decimal' | 'numeric', autoComplete: 'off' },
  };
}
