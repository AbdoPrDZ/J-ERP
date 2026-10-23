import type { FieldProps } from './registry';

export function FloatField({ field, value, onChange, readonly }: FieldProps) {
  return (
    <input
      type="number"
      step="any"
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
      value={value === null || value === undefined ? '' : String(value)}
      placeholder={field.label}
      readOnly={readonly}
      disabled={readonly}
      onChange={(event) =>
        onChange(event.target.value === '' ? null : Number(event.target.value))
      }
    />
  );
}
