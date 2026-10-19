'use client';
import { type ReactNode, useId, useState } from 'react';
import { Button, ErrorLine, Field, TextLink } from '@/components/ui';
import { ApiError, errorText, fieldErrors } from '@/lib/api';
import { type FormErrors, formErrorsFrom, MONTHS, type RuleForm, WEEKDAYS } from '@/features/repeats';
import s from './page.module.css';

type Built<B> = { ok: true; body: B } | { ok: false; errors: FormErrors };

/** Label, underline select and error line, like `Field` but for a list of choices. */
function SelectField({ label, error, value, onChange, children }: { label: string; error?: string; value: string; onChange: (v: string) => void; children: ReactNode }) {
  const id = useId();
  return (
    <div className="field">
      <label htmlFor={id} className="lbl">{label}</label>
      <select id={id} className={`uline ${s.sel} ${error ? 'err' : ''}`} aria-invalid={Boolean(error)} value={value} onChange={(e) => onChange(e.target.value)}>{children}</select>
      {error && <ErrorLine>{error}</ErrorLine>}
    </div>
  );
}

interface Props<B> {
  initial: RuleForm;
  /** Turns the form into a request body, or the reasons it cannot be sent yet. */
  build: (f: RuleForm) => Built<B>;
  /** Sends it; a rejected promise is shown under the form, field errors under their fields. */
  submit: (body: B) => Promise<unknown>;
  submitLabel: string;
  onCancel: () => void;
  /** Tags the person already uses, offered while typing. */
  tags: string[];
  /** The first-payment date box exists only when adding (a change applies from the next payment). */
  startsOn?: { min: string };
}

/** The add / change form of one repeating payment. It keeps what was typed when the server says no. */
export function RuleEditor<B>({ initial, build, submit, submitLabel, onCancel, tags, startsOn }: Props<B>) {
  const [f, setF] = useState(initial);
  const [errors, setErrors] = useState<FormErrors>({});
  const [failure, setFailure] = useState('');
  const [busy, setBusy] = useState(false);
  const listId = useId();
  const set = <K extends keyof RuleForm>(k: K) => (v: RuleForm[K]) => { setF((cur) => ({ ...cur, [k]: v })); setErrors((cur) => ({ ...cur, [k]: undefined })); };

  async function send() {
    setFailure('');
    const r = build(f);
    if (!r.ok) { setErrors(r.errors); return; }
    setBusy(true);
    try {
      await submit(r.body);
    } catch (e) {
      const fe = formErrorsFrom(fieldErrors(e));
      if (Object.keys(fe).length > 0) setErrors(fe);
      else setFailure(e instanceof ApiError && e.status < 500 ? e.message : errorText(e));
      setBusy(false);
    }
  }

  const longDay = f.kind !== 'weekly' && Number(f.day) > 28;
  return (
    <form className="well" onSubmit={(e) => { e.preventDefault(); void send(); }} noValidate>
      <div className={s.formGrid}>
        <Field label="Name" maxLength={80} autoComplete="off" placeholder="Rent" value={f.name} error={errors.name} onChange={(e) => set('name')(e.target.value)} />
        <Field label="Tag" placeholder="#tag" list={listId} autoComplete="off" value={f.tag} error={errors.tag} onChange={(e) => set('tag')(e.target.value)} />
        <Field label="Amount · ₹" inputMode="decimal" autoComplete="off" placeholder="15000" value={f.amount} error={errors.amount} onChange={(e) => set('amount')(e.target.value)} />
        <SelectField label="Repeats" value={f.kind} onChange={(v) => set('kind')(v as RuleForm['kind'])}>
          <option value="monthly">Every month</option>
          <option value="weekly">Every week</option>
          <option value="yearly">Every year</option>
        </SelectField>
        {f.kind === 'weekly' && (
          <SelectField label="On" value={f.weekday} error={errors.weekday} onChange={set('weekday')}>
            {WEEKDAYS.map((w) => <option key={w.value} value={w.value}>{w.name}</option>)}
          </SelectField>
        )}
        {f.kind === 'yearly' && (
          <SelectField label="Month" value={f.month} error={errors.month} onChange={set('month')}>
            {MONTHS.map((m, i) => <option key={m} value={i + 1}>{m}</option>)}
          </SelectField>
        )}
        {f.kind !== 'weekly' && (
          <Field label="Day of the month" type="number" min={1} max={31} inputMode="numeric" placeholder="1" value={f.day} error={errors.day} hint={longDay ? 'In shorter months it is paid on the last day.' : undefined} onChange={(e) => set('day')(e.target.value)} />
        )}
        {startsOn && <Field label="First payment on · optional" type="date" min={startsOn.min} value={f.startsOn} error={errors.startsOn} hint="Empty starts with the next one due." onChange={(e) => set('startsOn')(e.target.value)} />}
        <Field label="Last payment on · optional" type="date" value={f.endsOn} error={errors.endsOn} onChange={(e) => set('endsOn')(e.target.value)} />
        <Field label="Note · optional" maxLength={120} autoComplete="off" placeholder="Optional" value={f.note} error={errors.note} onChange={(e) => set('note')(e.target.value)} />
        <Field label="Payment words · optional" maxLength={100} autoComplete="off" placeholder="landlord, rent" value={f.hint} error={errors.hint} hint="A payee or tag word that links a payment you already logged." onChange={(e) => set('hint')(e.target.value)} />
      </div>
      <datalist id={listId}>{tags.map((t) => <option key={t} value={t} />)}</datalist>
      <div className={s.formActions}>
        <Button type="submit" disabled={busy}>{submitLabel}</Button>
        <TextLink mono onClick={onCancel}>Cancel</TextLink>
      </div>
      {failure && <div className={s.formErr}><ErrorLine>{failure}</ErrorLine></div>}
    </form>
  );
}
