import type { FieldProps } from './registry';

export function BooleanField({ value, onChange, readonly }: FieldProps) {
  return (
    <input
      type="checkbox"
      className="h-5 w-5 rounded border-slate-300 text-brand-blue focus:ring-brand-cyan/50"
      checked={Boolean(value)}
      disabled={readonly}
      onChange={(event) => onChange(event.target.checked)}
    />
  );
}
