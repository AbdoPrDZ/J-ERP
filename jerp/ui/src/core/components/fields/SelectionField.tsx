import type { FieldProps } from './registry';

export function SelectionField({ field, value, onChange, readonly }: FieldProps) {
  const options = field.selection ?? [];
  return (
    <select
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
      value={(value as string) ?? ''}
      disabled={readonly}
      onChange={(event) => onChange(event.target.value || null)}
    >
      <option value="">—</option>
      {options.map(([key, label]) => (
        <option key={key} value={key}>
          {label}
        </option>
      ))}
    </select>
  );
}
