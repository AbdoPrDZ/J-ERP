import type { FieldProps } from './registry';

export function DateField({ field, value, onChange, readonly }: FieldProps) {
  const text = value === null || value === undefined ? '' : String(value).slice(0, 10);
  return (
    <input
      type="date"
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
      value={text}
      readOnly={readonly}
      disabled={readonly}
      onChange={(event) => onChange(event.target.value || null)}
    />
  );
}
