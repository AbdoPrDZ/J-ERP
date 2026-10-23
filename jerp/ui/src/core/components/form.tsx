import { FieldHelp } from './fields/FieldHelp';
import { fieldRegistry } from './fields/registry';
import type { FormSchema } from '../types';

export interface FormProps {
  schema: FormSchema;
  values: Record<string, unknown>;
  onChange?: (name: string, value: unknown) => void;
  onSubmit?: (values: Record<string, unknown>) => void;
  readonly?: boolean;
}

export function Form({ schema, values, onChange, onSubmit, readonly }: FormProps) {
  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit?.(values);
      }}
    >
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {schema.fields.map((field) => {
          const Widget = fieldRegistry.get(field.ttype);
          return (
            <label key={field.name} className="block">
              <span className="mb-1 flex items-center gap-1.5 text-sm font-medium text-slate-700">
                {field.label}
                {field.required ? <span className="text-red-500">*</span> : null}
                {field.help ? <FieldHelp text={field.help} /> : null}
              </span>
              {Widget ? (
                <Widget
                  field={field}
                  value={values[field.name]}
                  readonly={readonly || field.readonly}
                  onChange={(value) => onChange?.(field.name, value)}
                />
              ) : (
                <span className="block text-sm text-red-600">
                  No widget registered for type “{field.ttype}”.
                </span>
              )}
            </label>
          );
        })}
      </div>
      {onSubmit && !readonly ? (
        <button
          type="submit"
          className="rounded bg-brand-blue px-4 py-2 text-sm font-medium text-white hover:bg-brand-blue-dark focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-cyan/60"
        >
          Save
        </button>
      ) : null}
    </form>
  );
}
