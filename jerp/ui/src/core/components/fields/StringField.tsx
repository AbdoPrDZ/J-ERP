import type { FieldProps } from './registry';

export function StringField({ field, value, onChange, readonly }: FieldProps) {
  return (
    <input
      type="text"
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-blue-500 focus:outline-none disabled:bg-slate-100"
      value={(value as string) ?? ''}
      placeholder={field.label}
      readOnly={readonly}
      disabled={readonly}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}
