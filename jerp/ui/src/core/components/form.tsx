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
              <span className="mb-1 block text-sm font-medium text-slate-700">
                {field.label}
                {field.required ? <span className="text-red-500"> *</span> : null}
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
              {field.help ? (
                <span className="mt-1 block text-xs text-slate-500">{field.help}</span>
              ) : null}
            </label>
          );
        })}
      </div>
      {onSubmit && !readonly ? (
        <button
          type="submit"
          className="rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          Save
        </button>
      ) : null}
    </form>
  );
}
