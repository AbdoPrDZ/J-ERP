import type { FieldProps } from './registry';
import { MultiLangPanel } from './MultiLangPanel';

export function StringField({
  field,
  value,
  onChange,
  readonly,
  model,
  recordId,
}: FieldProps) {
  return (
    <div className="relative">
      <input
        type="text"
        className="w-full rounded border border-slate-300 px-3 py-2 pr-10 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
        value={(value as string) ?? ''}
        placeholder={field.label}
        readOnly={readonly}
        disabled={readonly}
        onChange={(event) => onChange(event.target.value)}
      />
      {field.multi_language ? (
        <MultiLangPanel
          field={field}
          defaultValue={value === null || value === undefined ? '' : String(value)}
          modelName={model}
          recordId={recordId}
          readonly={readonly}
        />
      ) : null}
    </div>
  );
}
