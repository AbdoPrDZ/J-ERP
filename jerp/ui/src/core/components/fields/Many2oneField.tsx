import * as React from 'react';

import { model } from '../../model';
import type { FieldProps } from './registry';
import { StringField } from './StringField';

interface Option {
  id: number | string;
  _label?: string;
  name?: string;
}

/** Select widget for ``Many2oneField`` relations. */
export function Many2oneField({ field, value, onChange, readonly }: FieldProps) {
  const relation = field.relation ?? null;
  const [options, setOptions] = React.useState<Option[]>([]);

  React.useEffect(() => {
    if (!relation) {
      setOptions([]);
      return;
    }

    let cancelled = false;
    void (async () => {
      try {
        const rows = await model(relation).all<Option>({ limit: 200 });
        if (!cancelled) {
          setOptions(rows);
        }
      } catch {
        if (!cancelled) {
          setOptions([]);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [relation]);

  if (!relation) {
    return (
      <StringField
        field={field}
        value={value}
        onChange={onChange}
        readonly={readonly}
      />
    );
  }

  const current = value === null || value === undefined ? '' : String(value);
  const known = options.some((option) => String(option.id) === current);

  return (
    <select
      className="w-full rounded border border-slate-300 px-3 py-2 text-sm shadow-sm focus:border-brand-blue focus:outline-none focus:ring-2 focus:ring-brand-cyan/30 disabled:bg-slate-100"
      value={current}
      disabled={readonly}
      onChange={(event) =>
        onChange(event.target.value === '' ? null : Number(event.target.value))
      }
    >
      <option value="">-</option>
      {!known && current ? <option value={current}>#{current}</option> : null}
      {options.map((option) => (
        <option key={String(option.id)} value={String(option.id)}>
          {option._label ?? option.name ?? `#${option.id}`}
        </option>
      ))}
    </select>
  );
}
