import type { FieldProps } from './registry';

export function PasswordField({ field, value, onChange, readonly }: FieldProps) {
  return (
    <input
      type="password"
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
      value={(value as string) ?? ''}
      placeholder={field.label}
      readOnly={readonly}
      disabled={readonly}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
